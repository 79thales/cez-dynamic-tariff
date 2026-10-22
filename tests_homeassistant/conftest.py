"""Fixtures for tests running against a real Home Assistant installation."""

from __future__ import annotations

import asyncio
import socket
import sys
from unittest.mock import patch

import pytest
from aiohttp.resolver import ThreadedResolver

_windows_pair_patch = None
_windows_policy = None
_windows_loop_factory = None


def pytest_configure(config):
    """Windows asyncio potřebuje TCP socketpair i při zákazu externí sítě.

    Plugin HA dovoluje unix socketpair, který Windows nemá. Uvolníme jen
    konstruktor uvnitř standardního socketpair; zákaz běžných socketů
    a kontrola connect na loopback zůstávají. Linux CI běží beze změny.
    """
    global _windows_pair_patch, _windows_policy, _windows_loop_factory
    if sys.platform != "win32":
        return
    # HA plugin záměrně zakazuje nahrazení celé policy, proto obyčejná
    # event_loop_policy fixture nemá účinek. Zachováme HA policy včetně jeho
    # executorů a kontroly chyb, změníme pouze její Windows I/O backend.
    # Selector dokončí ukončení HTTP accept před kontrolou úniku úloh;
    # žádnou úlohu nepřeskakujeme a skutečné HTTP testy zůstávají zapnuté.
    _windows_policy = asyncio.get_event_loop_policy()
    _windows_loop_factory = _windows_policy._loop_factory
    _windows_policy._loop_factory = asyncio.SelectorEventLoop
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
    if _windows_policy is not None:
        _windows_policy._loop_factory = _windows_loop_factory


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
