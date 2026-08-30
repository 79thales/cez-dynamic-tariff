"""Fixtures for tests running against a real Home Assistant installation."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def enable_test_custom_integrations(enable_custom_integrations):
    """Enable loading integrations from this repository's custom_components."""
    yield
