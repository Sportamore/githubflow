# coding=utf-8
import logging
import re
from datetime import date

from agithub.GitHub import GitHub

import config

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

github = GitHub(token=config.GITHUB_TOKEN)


class ValidationError(Exception):
    pass


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


def review_pr(pull_request, action, comment):
    logger.info("Reviewing %s, %s", pull_request["number"], action)
    repo = get_pr_repo(pull_request)
    pr_obj = repo.pulls[pull_request["number"]]
    create_or_fail(
        pr_obj.reviews,
        {
            "body": comment,
            "event": action
        }
    )


def pull_request_modified(pull_request):
    logger.info("Init checks for PR #%s", pull_request["number"])

    if pull_request["base"]["ref"] == config.STABLE_BRANCH:
        check_release_pr(pull_request)

    else:
        logger.info("Unmonitored branch: %s", pull_request["base"]["ref"])


def check_release_pr(pull_request):
    set_pr_status(pull_request, "pending", "Validating release")

    try:
        assert_valid_title(pull_request)
        assert_valid_body(pull_request)
        assert_valid_tag(pull_request)

    except ValidationError as e:
        logger.exception("Validation failed: %s", e)
        fail_pr(pull_request, str(e))

    except Exception:
        logger.exception("Validation error")
        set_pr_status(pull_request, "error", "Validation error")

    else:
        logger.info("All status checks passed")
        approve_pr(pull_request)


def assert_valid_title(pull_request):
    pr_title = pull_request["title"]

    if re.match(config.RELEASE_PATTERN_SEMVER, pr_title):
        return True

    elif re.match(config.RELEASE_PATTERN_DATE, pr_title):
        if pr_title[:8] != date.today().strftime('%Y%m%d'):
            raise ValidationError("Release date not current")

        else:
            return True

    else:
        raise ValidationError("Invalid release title")


def assert_valid_body(pull_request):
    if not len(pull_request["body"]):
        raise ValidationError("Missing description")


def assert_valid_tag(pull_request):
    repo = get_pr_repo(pull_request)
    status, response = repo.releases.tags[pull_request["title"]].get()
    if status == 200:
        raise ValidationError("Tag exists")


def fail_pr(pull_request, reason):
    logger.info("Failing PR #%s", pull_request["number"])
    set_pr_status(pull_request, "failure", reason)
    review_pr(pull_request,
              ("REQUEST_CHANGES" if config.APPROVE_RELEASES else "COMMENT"),
              reason)


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
        review_pr(pull_request,
                  "APPROVE" if config.APPROVE_RELEASES else "COMMENT",
                  "Valid release")


def pull_request_merged(pull_request):
    logger.info("Init final action for PR #%s", pull_request["number"])

    base_ref = pull_request["base"]["ref"]
    if base_ref == config.STABLE_BRANCH:
        create_release(pull_request)

    elif base_ref == config.DEVELOPMENT_BRANCH:
        suggest_release_note(pull_request)

    else:
        logger.info("Unmonitored branch: %s", base_ref)


def create_release(pull_request):
    logger.info("Creating release from PR #%s", pull_request["number"])

    # TODO: Add more last-minute validation (or check statuses?)
    assert_valid_tag(pull_request)

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


def suggest_release_note(pull_request):
    logger.info("Suggesting release note in PR #%s", pull_request["number"])

    title = pull_request["title"]
    match = re.match(config.JiraConfig.TITLE_PATTERN, title)

    if match and config.JiraConfig.BROWSE_URL:
        note = "- {description} [[{issue}]({url}{issue})]".format(
            url=config.JiraConfig.BROWSE_URL,
            **match.groupdict()
        )
        review_pr(pull_request, "COMMENT",
                  ("Suggested release note:\n"
                   "{note}\n```\n{note}\n```".format(note=note)))

    else:
        logger.warning("No issue tag detected")
