# -*- coding: utf-8 -*-
from unittest import TestCase, skip

try:
    from mock import MagicMock, patch
except ImportError:
    from unittest.mock import MagicMock, patch

__all__ = ['TestCase', 'MagicMock', "patch", "skip", "make_pull_request"]


def make_pull_request(ref="some-ref"):
    return {
        "number": 1,
        "title": "",
        "body": "",
        "base": {
            "ref": ref,
        },
        "merge_commit_sha": "aabbcc",
        "merged": False,
    }
