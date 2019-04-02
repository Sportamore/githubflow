# coding=utf-8
from os import environ as env


class FlaskConfig(object):
    DEBUG = False


class JiraConfig(object):
    DEBUG = False

    TITLE_PATTERN = (r'^'
                     r'(?P<issue>[A-Z]{2,10}-[0-9]{1,10})'
                     r'[:\s]+'
                     r'(?P<description>[\w\s"\'.()\[\]_-]+$)')
    BROWSE_URL = env.get("JIRA_BROWSE_URL", None)


# Application
LOG_LEVEL = env.get("LOG_LEVEL", "INFO").upper()

# Repo defaults
STABLE_BRANCH = "master"
DEVELOPMENT_BRANCH = "dev"

# Releases
APPROVE_RELEASES = bool(env.get("APPROVE_RELEASES", False))
RELEASE_PATTERN_SEMVER = r"^\d+\.\d+\.\d+$"
RELEASE_PATTERN_DATE = r"^\d{8}\.\d+$"

# Secrets
WEBHOOK_SECRET = env.get("GITHUB_WEBHOOK_SECRET").encode('utf-8')
GITHUB_TOKEN = env.get("GITHUB_TOKEN")
