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


def set_commit_status(repo, commit, status, description):
    logger.info("Settings status of %s to %s", commit, status)
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
    repo = get_pr_repo(pull_request)

    # Not always avaiable immediately after a PR is opened
    commit = pull_request.get("merge_commit_sha")
    if not commit:
        logger.warning("Merge commit not available.")
        return False

    logger.debug("Settings status to pending")
    set_commit_status(repo, commit, "pending", "Parsing pull request")

    try:
        assert_valid_title(pull_request)
        assert_valid_body(pull_request)

    except ValidationError as e:
        logger.exception("Validation failed")
        set_commit_status(repo, commit, "failure", e.message)

    except Exception:
        logger.exception("Validation error")
        set_commit_status(repo, commit, "error", "Validation error")

    else:
        set_commit_status(repo, commit, "success", "Valid release")
        if config.APPROVE_RELEASES:
            approve_pr.delay(pull_request)


@app.task()
def approve_pr(pull_request):
    logger.info("Approving PR #%s", pull_request["number"])

    repo = get_pr_repo(pull_request)
    pr_obj = repo.pulls[pull_request["number"]]

    status, response = pr_obj.reviews.get()
    current_user_id = github.user.get()[1]["id"]

    logger.debig("Fetched %s reviews")
    for review in response:
        if review["user"]["id"] == current_user_id:
            logger.warning("PR already reviews by GitHubFlow")
            return False

    else:
        create_or_fail(
            pr_obj.reviews,
            {
                "body": "Valid release",
                "event": "APPROVE"
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
