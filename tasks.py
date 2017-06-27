# coding=utf-8
import logging
import re

from celery import Celery
from requests import post
from agithub.GitHub import GitHub

import config

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = Celery(__name__)
app.config_from_object(config.CeleryConfig)

github = GitHub(token=config.GITHUB_TOKEN)


def assert_valid_title(title):
    if not re.match(config.RELEASE_PATTERN, title):
        raise ValueError("! %r =~ %r", title, config.RELEASE_PATTERN)


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
            "status": status,
            "description": description
        }
    )


@app.task()
def check_pull_request(pull_request):
    logger.info("Init status checks for PR #%s", pull_request["number"])
    repo = get_pr_repo(pull_request)
    commit = pull_request["head"]["sha"]

    logger.debug("Settings status to pending")
    set_commit_status(repo, commit, "pending", "Parsing pull request")

    try:
        # TODO: Validate body?
        assert_valid_title(pull_request["title"])

    except ValueError:
        set_commit_status(repo, commit, "failure", "Invalid title")

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
    assert_valid_title(pull_request["title"])

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


@app.task()
def notify_slack(release, repo):
    logger.info("Notifying slack about relase: %s", release["tag_name"])

    body = "New release in <{}|{}>: <{}|{}>.".format(
        repo["html_url"], repo["full_name"],
        release["html_url"], release["tag_name"])

    res = post(config.SLACK_WEBHOOK, json={"text": body})
    logger.debug("Slack response: %s", res.status_code)

    if res.status_code != 200:
        raise Exception(
            "Slack notification failed with code: {}, message: {}".format(
                res.status_code, res.content))
