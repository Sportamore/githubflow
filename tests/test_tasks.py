# -*- coding: utf-8 -*-
from githubflow import tasks, settings

from . import TestCase, patch


def make_pull_request(ref="some-ref"):
    return {
        "number": 1,
        "title": "",
        "body": "",
        "base": {
            "ref": ref,
        },
        "merge_commit_sha": "aabbcc",
    }


class TestHandlers(TestCase):
    unrelated_pr = make_pull_request("some-branch")
    stable_pr = make_pull_request(settings.STABLE_BRANCH)
    development_pr = make_pull_request(settings.DEVELOPMENT_BRANCH)

    @patch("githubflow.tasks.check_release_pr")
    def test_handle_pr_modified(self, mock_check):
        tasks.handle_pr_modified(self.unrelated_pr)
        self.assertEqual(mock_check.call_count, 0)

        tasks.handle_pr_modified(self.stable_pr)
        mock_check.assert_called_with(self.stable_pr)

    @patch("githubflow.tasks.create_release")
    @patch("githubflow.tasks.suggest_release_note")
    def test_handle_pr_merged(self, mock_suggest, mock_create):
        tasks.handle_pr_merged(self.unrelated_pr)
        self.assertEqual(mock_suggest.call_count, 0)
        self.assertEqual(mock_create.call_count, 0)

        tasks.handle_pr_merged(self.stable_pr)
        mock_create.assert_called_once_with(self.stable_pr)

        tasks.handle_pr_merged(self.development_pr)
        mock_suggest.assert_called_once_with(self.development_pr)


@patch("githubflow.tasks.create_or_fail")
class TestValidators(TestCase):
    @patch("githubflow.tasks.assert_valid_tag")
    @patch("githubflow.tasks.set_pr_status")
    def test_check_release_pr(self, mock_status, mock_assert, mock_create):
        pull_request = make_pull_request()

        with patch("githubflow.tasks.fail_pr") as mock_fail:
            tasks.check_release_pr(pull_request)
            mock_fail.assert_called()

        pull_request["title"] = "1.2.3"
        with patch("githubflow.tasks.fail_pr") as mock_fail:
            tasks.check_release_pr(pull_request)
            mock_fail.assert_called()

        pull_request["body"] = "some-body"
        with patch("githubflow.tasks.approve_pr") as mock_approve:
            tasks.check_release_pr(pull_request)
            mock_approve.assert_called()

        mock_assert.side_effect = tasks.ValidationError('foo')
        with patch("githubflow.tasks.fail_pr") as mock_fail:
            tasks.check_release_pr(pull_request)
            mock_fail.assert_called()

        mock_assert.side_effect = KeyError('foo')
        tasks.check_release_pr(pull_request)
        self.assertIn("error", mock_status.call_args[0])
