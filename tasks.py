# coding=utf-8
import logging
import re

from Celery import Celery
from github import Github
from Request import post

import config

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = Celery(__name__)
app.config_from_object(config.CeleryConfig)

github = Github(config.GITHUB_TOKEN)


@app.task()
def release_from_pr(pull_request):
    logger.info("Creating release from PR #%S", pull_request["number"])

    if not re.match(config.RELEASE_PATTERN, pull_request["title"]):
        logger.error("Invalid PR title: %s", pull_request["title"])
        return False

    base = pull_request[".base"]["repo"]
    owner = base["owner"]["login"]
    repo = github.get_user(owner).get_repo(base["name"])

    repo.create_git_tag_and_release(
        tag=pull_request["title"],
        tag_message="Merged Pull Request #{}".format(pull_request["number"]),
        release_name=pull_request["title"],
        release_message=pull_request["title"],
        object=pull_request["merge_commit_sha"],
        type="commit"
    )


@app.task()
def notify_slack(release, repo):
    logger.info("Notifying slack about relase: %s", release["tag_name"])

    body = "New release, repo: {}, tag: {}".format(
        repo["full_name"]. release["tag_name"])

    post(config.SLACK_WEBHOOK, json={"text": body})
