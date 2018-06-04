# coding=utf-8
import logging
import re

from celery import Celery
from agithub.GitHub import GitHub

import config

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = Celery(__name__)
app.config_from_object(config.CeleryConfig)

github = GitHub(token=config.GITHUB_TOKEN)


class ValidationError(Exception):
    pass


def assert_valid_title(pull_request):
    if not re.match(config.RELEASE_PATTERN, pull_request["title"]):
        raise ValidationError("Invalid release title")


def assert_valid_body(pull_request):
    if not len(pull_request["body"]):
        raise ValidationError("Missing description")


def assert_valid_tag(pull_request):
    repo = get_pr_repo(pull_request)
    status, response = repo.releases.tags[pull_request["title"]].get()
    if status == 200:
        raise ValidationError("Tag exists")


def get_pr_repo(pull_request):
    """ Create an agithub repo partial from a pull_request event """
    base = pull_request["base"]["repo"]
    owner = base["owner"]["login"]
    return github.repos[owner][base["name"]]


def create_or_fail(partial, request):
    status, response = partial.post(body=request)
    if status not in (200, 201):
        raise Exception(
            "Creation failed, request: {!r}, "
            "response: {!r}, code: {}".format(
                request, response, status))


def set_pr_status(pull_request, status, description):
    commit = pull_request["head"]["sha"]
    logger.info("Settings status of %s to %s", commit, status)

    repo = get_pr_repo(pull_request)
    create_or_fail(
        repo.statuses[commit],
        {
            "context": "GitHubFlow",
            "state": status,
            "description": description
        }
    )


@app.task()
def check_pull_request(pull_request):
    logger.info("Init status checks for PR #%s", pull_request["number"])
    set_pr_status(pull_request, "pending", "Validating release")

    try:
        assert_valid_title(pull_request)
        assert_valid_body(pull_request)
        assert_valid_tag(pull_request)

    except ValidationError as e:
        logger.exception("Validation failed: %s", e)
        fail_pr.delay(pull_request, str(e))

    except Exception:
        logger.exception("Validation error")
        set_pr_status(pull_request, "error", "Validation error")

    else:
        logger.info("All status checks passed")
        approve_pr.delay(pull_request)


@app.task()
def fail_pr(pull_request, reason):
    logger.info("Failing PR #%s", pull_request["number"])
    set_pr_status(pull_request, "failure", reason)

    repo = get_pr_repo(pull_request)
    pr_obj = repo.pulls[pull_request["number"]]
    create_or_fail(
        pr_obj.reviews,
        {
            "body": reason,
            "event": ("REQUEST_CHANGES" if config.APPROVE_RELEASES
                      else "COMMENT")
        }
    )


@app.task()
def approve_pr(pull_request):
    logger.info("Approving PR #%s", pull_request["number"])
    set_pr_status(pull_request, "success", "Valid release")

    repo = get_pr_repo(pull_request)
    pr_obj = repo.pulls[pull_request["number"]]

    status, response = pr_obj.reviews.get()
    current_user_id = github.user.get()[1]["id"]

    logger.debug("Fetched %s reviews")
    for review in response:
        if (review["user"]["id"] == current_user_id and
                review["state"] != "CHANGES_REQUESTED"):

            logger.warning("PR already approved by GitHubFlow")
            return False

    else:
        logger.info("Updating PR status")
        repo = get_pr_repo(pull_request)
        pr_obj = repo.pulls[pull_request["number"]]
        create_or_fail(
            pr_obj.reviews,
            {
                "body": "Valid release",
                "event": "APPROVE" if config.APPROVE_RELEASES else "COMMENT"
            }
        )


@app.task()
def release_from_pr(pull_request):
    logger.info("Creating release from PR #%s", pull_request["number"])

    # TODO: Add more last-minute validation (or check statuses?)
    assert_valid_title(pull_request)

    repo = get_pr_repo(pull_request)
    create_or_fail(
        repo.releases,
        {
            "tag_name": pull_request["title"],
            "target_commitish": pull_request["merge_commit_sha"],
            "name": pull_request["title"],
            "body": pull_request["body"]
        }
    )
