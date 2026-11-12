"""JSON API endpoints."""

from __future__ import annotations

from aceest import __version__


def test_health(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.get_json()
    assert body["status"] == "healthy"
    assert body["version"] == __version__
    assert body["track"] == "test"


def test_every_response_carries_release_headers(client):
    response = client.get("/api/programs")
    assert response.headers["X-ACEest-Version"] == __version__
    assert response.headers["X-ACEest-Track"] == "test"


def test_programs_listing(client):
    body = client.get("/api/programs").get_json()
    assert body["count"] == 3
    assert {p["code"] for p in body["programs"]} == {"FL", "MG", "BG"}


def test_program_detail_is_case_insensitive(client):
    response = client.get("/api/programs/mg")
    assert response.status_code == 200
    assert response.get_json()["name"] == "Muscle Gain (MG)"


def test_unknown_program_is_a_json_404(client):
    response = client.get("/api/programs/zz")
    assert response.status_code == 404
    assert response.get_json() == {"error": "NotFoundError", "message": "program 'zz' not found"}


def test_unknown_api_route_answers_in_json(client):
    response = client.get("/api/nothing-here")
    assert response.status_code == 404
    assert response.is_json


def test_site_metrics(client):
    assert client.get("/api/site").get_json()["capacity_users"] == 150
