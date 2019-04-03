# -*- coding: utf-8 -*-
from githubflow import app, pr_event

from . import TestCase, patch, make_pull_request
from time import sleep


class TestAPI(TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        self.client = app.test_client()

    @patch("githubflow.pr_event")
    @patch("githubflow.settings")
    @patch("githubflow.validate_signature")
    def test_webhook(self, mock_validate, mock_settings, mock_pr_event):
        res = self.client.get('/')
        self.assertEqual(res.status_code, 405)

        mock_settings.IS_CONFIGURED = False
        res = self.client.post('/')
        self.assertEqual(res.status_code, 500)

        mock_settings.IS_CONFIGURED = True
        mock_validate.side_effect = ValueError("bad digest")
        res = self.client.post('/')
        self.assertEqual(res.status_code, 403)

        mock_validate.side_effect = None
        res = self.client.post('/')
        self.assertEqual(res.status_code, 400)

        request_headers = {
            "X-GitHub-Delivery": "delivery-id",
            "X-GitHub-Event": "some-event"
        }
        request_body = {"a": "b"}
        res = self.client.post('/', headers=request_headers, json=request_body)
        self.assertEqual(res.status_code, 200)
        mock_pr_event.assert_not_called()

        request_headers["X-GitHub-Event"] = "pull_request"
        res = self.client.post('/', headers=request_headers, json=request_body)
        self.assertEqual(res.status_code, 200)
        mock_pr_event.assert_called_with(request_body)

    @patch("githubflow.handle_pr_modified")
    @patch("githubflow.handle_pr_merged")
    def test_pr_event(self, mock_merged, mock_modified):
        pull_request = make_pull_request()
        payload = {
            "action": "some-event",
            "pull_request": pull_request,
        }

        pr_event(payload)
        mock_modified.assert_not_called()
        mock_merged.assert_not_called()

        payload["action"] = "edited"
        pr_event(payload)
        mock_modified.assert_called_with(pull_request)

        payload["action"] = "closed"
        pull_request["merged"] = False
        pr_event(payload)
        sleep(1)
        mock_merged.assert_not_called()

        pull_request["merged"] = True
        pr_event(payload)
        sleep(1)
        mock_merged.assert_called_with(pull_request)
