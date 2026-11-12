"""Shared fixtures."""

from __future__ import annotations

import pytest

from aceest import create_app


@pytest.fixture()
def app():
    return create_app("testing", overrides={"SECRET_KEY": "test-key", "TRACK": "test"})


@pytest.fixture()
def client(app):
    return app.test_client()
