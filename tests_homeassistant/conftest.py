"""Fixtures for tests running against a real Home Assistant installation."""

from __future__ import annotations

import socket
import sys
from unittest.mock import patch

import pytest
from aiohttp.resolver import ThreadedResolver

_windows_pair_patch = None


def pytest_configure(config):
    """Windows asyncio potřebuje TCP socketpair i při zákazu externí sítě.

    Plugin HA dovoluje unix socketpair, který Windows nemá. Uvolníme jen
    konstruktor uvnitř standardního socketpair; zákaz běžných socketů
    a kontrola connect na loopback zůstávají. Linux CI běží beze změny.
    """
    global _windows_pair_patch
    if sys.platform != "win32":
        return
    original = socket.socketpair
    constructor = socket.socket

    def loopback_pair(*args, **kwargs):
        with patch("socket.socket", constructor):
            return original(*args, **kwargs)

    # Patch musí být aktivní již při vytvoření event_loop fixture i při
    # její závěrečné náhradě čistou smyčkou, tedy po celou pytest session.
    _windows_pair_patch = patch("socket.socketpair", loopback_pair)
    _windows_pair_patch.start()


def pytest_unconfigure(config):
    if _windows_pair_patch is not None:
        _windows_pair_patch.stop()


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
