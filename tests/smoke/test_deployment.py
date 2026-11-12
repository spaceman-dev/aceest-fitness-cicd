"""Post-deployment smoke tests.

Not part of the unit run. The pipeline runs them from the test image against a
live endpoint after every rollout step, e.g.

    docker run --rm --network aceest-net \\
        -e ACEEST_BASE_URL=http://192.168.89.2 \\
        -e ACEEST_HOST=canary.aceest.localhost \\
        -e ACEEST_EXPECT_VERSION=1.0.0 \\
        aceest-fitness-test:<tag> pytest -o addopts="" tests/smoke
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request

import pytest

BASE_URL = os.environ.get("ACEEST_BASE_URL", "").rstrip("/")
HOST = os.environ.get("ACEEST_HOST", "")
EXPECTED_VERSION = os.environ.get("ACEEST_EXPECT_VERSION", "")
EXTRA_HEADER = os.environ.get("ACEEST_EXTRA_HEADER", "")

pytestmark = pytest.mark.skipif(not BASE_URL, reason="ACEEST_BASE_URL is not set")


def call(path, payload=None):
    headers = {"Accept": "application/json"}
    if HOST:
        headers["Host"] = HOST
    if EXTRA_HEADER:
        name, _, value = EXTRA_HEADER.partition(":")
        headers[name.strip()] = value.strip()
    data = None
    if payload is not None:
        data = json.dumps(payload).encode()
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(BASE_URL + path, data=data, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status, response.read().decode()
    except urllib.error.HTTPError as error:
        return error.code, error.read().decode()


def test_health_reports_the_expected_version():
    # right after a switch the ingress may still be reloading, so allow it a moment
    deadline = time.monotonic() + 30
    while True:
        try:
            status, text = call("/api/health")
        except OSError as error:  # connection refused/reset or timeout while endpoints settle
            status, text = 0, str(error)
        body = json.loads(text) if status == 200 else {}
        if status == 200 and body.get("version", "") == (EXPECTED_VERSION or body.get("version")):
            break
        if time.monotonic() > deadline:
            pytest.fail(f"wanted version {EXPECTED_VERSION or 'any'}, got {status}: {text[:200]}")
        time.sleep(2)
    assert body["status"] == "healthy"


def test_dashboard_renders():
    status, text = call("/")
    assert status == 200
    assert "ACEest FUNCTIONAL FITNESS" in text


def test_program_catalogue_is_served():
    status, text = call("/api/programs")
    assert status == 200
    assert json.loads(text)["count"] >= 3
