# -*- coding: utf-8 -*-
import hmac

from githubflow.utils import validate_signature

from . import TestCase, MagicMock, patch


class TestUtils(TestCase):
    @patch("githubflow.utils.settings")
    def test_validate_signature(self, settings):
        settings.WEBHOOK_SECRET = b"abc123"

        request = MagicMock()
        request.data = b"This is a message"

        request.headers = {"X-Hub-Signature": "sha1=111222333"}
        self.assertRaises(ValueError, validate_signature, request)

        signature = hmac.new(settings.WEBHOOK_SECRET, request.data, "sha1")
        request.headers = {
            "X-Hub-Signature": "sha1=" + signature.hexdigest()
        }
        self.assertTrue(validate_signature(request))
