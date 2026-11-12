"""Shared fixtures."""

from __future__ import annotations

import pytest

from aceest import create_app

TEST_SETTINGS = {
    "SECRET_KEY": "test-key",
    "TRACK": "test",
    # form tests post without a browser session; test_web covers CSRF itself
    "WTF_CSRF_ENABLED": False,
}


@pytest.fixture()
def app():
    return create_app("testing", overrides=TEST_SETTINGS)


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def csrf_client():
    app = create_app("testing", overrides={**TEST_SETTINGS, "WTF_CSRF_ENABLED": True})
    return app.test_client()


@pytest.fixture()
def profile_payload():
    return {"name": "Ravi Kumar", "age": 32, "weight_kg": 80, "program": "MG", "adherence": 85}
