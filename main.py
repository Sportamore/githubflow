#!/usr/bin/env python3
# coding=utf-8
import logging
import hmac

from flask import Flask, request, abort

import config
from tasks import release_from_pr, notify_slack

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config.from_object(config.FlaskConfig)


def validate_signature():
    logger.debug("Validating request digest")

    supplied_hmac = request.headers["X-Hub-Signature"]
    real_hmac = hmac.new(config.WEBHOOK_SECRET, request.data)
    if not hmac.compare_digest(supplied_hmac, real_hmac.hexdigest()):
        raise ValueError("Invalid HMAC")


def pr_event(payload):
    pull_request = payload["pull_request"]
    logger.debug("New event for PR #%s: %s",
                 pull_request["number"], payload["action"])

    if pull_request["base"]["ref"] != config.TARGET_BRANCH:
        logger.warning("Unmonitored branch")

    if payload["action"] in ("opened", "reopened", "synchronized"):
        # TODO:: Add status checks for content
        pass

    elif payload["action"] == "closed":
        if pull_request["merged"]:
            logger.info("PR merged, creating release")
            release_from_pr.delay(pull_request)

        else:
            logger.warning("PR closed")

    else:
        logger.warning("Unhandled PR action: %s", payload["action"])


def release_published(release, repo):
    logger.debug("New release: %s", release["tag_name"])

    if config.SLACK_WEBHOOK:
        notify_slack.delay(release, repo)


@app.route('/', methods=['POST'])
def handle_webhook():
    try:
        validate_signature()

    except Exception:
        logger.error("Refusing request, bad digest")
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

    elif event == "release":
        release_published(payload["release"], payload["repository"])

    else:
        logger.warning("Unhandled event: %s(%s)", event, payload.get("action"))

    return ""


if __name__ == "__main__":
    logger.setLevel(logging.DEBUG)
    app.run(debug=True)