"""Shared fixtures."""

from __future__ import annotations

import os
import tempfile

import pytest

# Anything that builds an app without overrides (e.g. importing the WSGI
# module) must not drop a database file into the working tree.
os.environ.setdefault("ACEEST_DB", os.path.join(tempfile.mkdtemp(), "aceest.db"))

from aceest import create_app  # noqa: E402

TEST_SETTINGS = {
    "SECRET_KEY": "test-key",
    "TRACK": "test",
    # form tests post without a browser session; test_web covers CSRF itself
    "WTF_CSRF_ENABLED": False,
}


@pytest.fixture()
def app(tmp_path):
    return create_app("testing", overrides={**TEST_SETTINGS, "DATABASE": str(tmp_path / "t.db")})


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def csrf_client(tmp_path):
    app = create_app("testing", overrides={
        **TEST_SETTINGS, "WTF_CSRF_ENABLED": True, "DATABASE": str(tmp_path / "csrf.db"),
    })
    return app.test_client()


@pytest.fixture()
def profile_payload():
    return {"name": "Ravi Kumar", "age": 32, "weight_kg": 80, "program": "MG", "adherence": 85}


@pytest.fixture()
def enrolled(client, profile_payload):
    response = client.post("/api/clients", json=profile_payload)
    assert response.status_code == 201
    return response.get_json()
