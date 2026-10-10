"""Fixtures for tests running against a real Home Assistant installation."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from aiohttp.resolver import ThreadedResolver


@pytest.fixture(autouse=True)
def enable_test_custom_integrations(enable_custom_integrations):
    """Enable loading integrations from this repository's custom_components."""
    yield


@pytest.fixture(autouse=True)
def loopback_http_resolver():
    """Loopback clients do not need pycares' process-wide shutdown thread.

    Older HA test plugins reject that persistent DNS-library thread during
    cleanup. Use aiohttp's standard resolver for local HTTP clients; the
    existing socket fixture still blocks external connections.
    """
    with patch("aiohttp.connector.DefaultResolver", ThreadedResolver):
        yield
