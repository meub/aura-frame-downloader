"""Shared fixtures. Tests never touch the network or the real saved app settings."""

import os

# Must be set before PyQt6 creates the application: run without a display.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
import requests  # noqa: E402

import aura.core as core  # noqa: E402


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """Fail any test that would make a real HTTP request (requests.get also goes through here)."""
    def refuse(*args, **kwargs):
        raise AssertionError("a test tried to use the network")
    monkeypatch.setattr(requests.Session, "request", refuse)


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    """The download loop waits between photos; tests shouldn't."""
    monkeypatch.setattr(core.time, "sleep", lambda seconds: None)


@pytest.fixture(scope="session")
def qapp():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])
