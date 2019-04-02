# coding=utf-8
import logging
import hmac

from . import settings

logger = logging.getLogger(__name__)


def validate_signature(request):
    logger.debug("Validating request digest")

    mode, digest = request.headers["X-Hub-Signature"].split('=')
    real_hmac = hmac.new(settings.WEBHOOK_SECRET, request.data, mode)
    if not hmac.compare_digest(digest, real_hmac.hexdigest()):
        raise ValueError("Invalid HMAC")

    else:
        return True
