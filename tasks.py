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


@app.task()
def release_from_pr(pull_request):
    logger.info("Creating release from PR #%s", pull_request["number"])

    if not re.match(config.RELEASE_PATTERN, pull_request["title"]):
        logger.error("Invalid PR title: %s", pull_request["title"])
        return False

    base = pull_request["base"]["repo"]
    owner = base["owner"]["login"]

    release = {
        "tag_name": pull_request["title"],
        "target_commitish": pull_request["merge_commit_sha"],
        "name": pull_request["title"],
        "body": pull_request["body"]
    }

    repo = github.repos[owner][base["name"]]
    status, response = repo.releases.post(body=release)
    if status != 201:
        logger.error("Release was not created, response: %r", response)
        return False


@app.task()
def notify_slack(release, repo):
    logger.info("Notifying slack about relase: %s", release["tag_name"])

    body = "New release in <{}|{}>: <{}|{}>.".format(
        repo["html_url"], repo["full_name"],
        release["html_url"], release["tag_name"])

    res = post(config.SLACK_WEBHOOK, json={"text": body})
    logger.debug("Slack response: %s", res.status_code)

    if res.status_code != 200:
        logger.error("Slack notification failed with code: %s, message: %s",
                     res.status_code, res.content)
        return False
