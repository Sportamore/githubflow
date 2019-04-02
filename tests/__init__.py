# -*- coding: utf-8 -*-
from unittest import TestCase, skip

try:
    from mock import MagicMock, patch
except ImportError:
    from unittest.mock import MagicMock, patch

__all__ = ['TestCase', 'MagicMock', "patch", "skip"]
