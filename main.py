#!/usr/bin/env python3
# coding=utf-8
import logging
import hmac

from flask import Flask, request, abort

import config
from tasks import release_from_pr, check_release_pr, check_pull_request

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config.from_object(config.FlaskConfig)


def validate_signature():
    logger.debug("Validating request digest")

    mode, digest = request.headers["X-Hub-Signature"].split('=')
    real_hmac = hmac.new(config.WEBHOOK_SECRET, request.data, mode)
    if not hmac.compare_digest(digest, real_hmac.hexdigest()):
        raise ValueError("Invalid HMAC")


def pr_event(payload):
    pull_request = payload["pull_request"]
    logger.debug("New event for PR #%s: %s",
                 pull_request["number"], payload["action"])

    if pull_request["base"]["ref"] == config.TARGET_BRANCH:
        if payload["action"] in ("opened", "reopened", "edited", "synchronize"):
            logger.info("PR created/updated, dispatching status check")
            check_release_pr.delay(pull_request)

        elif payload["action"] == "closed":
            if pull_request["merged"]:
                logger.info("PR merged, creating release")
                release_from_pr.delay(pull_request)

            else:
                logger.warning("PR closed")

        else:
            logger.info("Unhandled PR action: %s", payload["action"])
    elif pull_request["base"]["ref"] == config.DEVELOPMENT_BRANCH:
        check_pull_request.delay(pull_request)

    logger.warning("Unmonitored branch: %s", pull_request["base"]["ref"])
    return False


@app.route('/', methods=['POST'])
def handle_webhook():
    try:
        validate_signature()

    except Exception:
        logger.exception("Refusing request, bad digest")
        abort(403)

    try:
        delivery = request.headers["X-GitHub-Delivery"]
        event = request.headers["X-GitHub-Event"]
        payload = request.get_json()

    except Exception:
        logger.exception("Invalid request")
        abort(400)

    logger.debug("Handling delivery: %s", delivery)
    if event == "pull_request":
        pr_event(payload)

    else:
        logger.warning("Unhandled event: %s(%s)", event, payload.get("action"))

    return ""


if __name__ == "__main__":
    logger.setLevel(logging.DEBUG)
    app.run(debug=True)
