# -*- coding: utf-8 -*-
from unittest import TestCase

try:
    from mock import MagicMock
except ImportError:
    from unittest.mock import MagicMock

__all__ = ['TestCase', 'MagicMock']
