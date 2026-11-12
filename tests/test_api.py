"""JSON API endpoints."""

from __future__ import annotations

import pytest

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


def test_calorie_estimate(client):
    response = client.post("/api/calories", json={"weight_kg": 80, "program": "mg"})
    assert response.status_code == 200
    assert response.get_json() == {
        "weight_kg": 80.0, "program": "MG", "program_name": "Muscle Gain (MG)",
        "factor": 35, "calories": 2800,
    }


@pytest.mark.parametrize(("payload", "field"), [
    ({"program": "MG"}, "weight_kg"),
    ({"weight_kg": 80}, "program"),
    ({"weight_kg": 10, "program": "MG"}, "weight_kg"),
    ({"weight_kg": 80, "program": "XX"}, "program"),
])
def test_calorie_estimate_rejects_bad_input(client, payload, field):
    response = client.post("/api/calories", json=payload)
    assert response.status_code == 400
    assert response.get_json()["field"] == field


def test_non_json_body_is_rejected(client):
    response = client.post("/api/calories", data="weight=80")
    assert response.status_code == 400
    assert response.get_json()["message"] == "request body must be a JSON object"


def test_profile_endpoint(client, profile_payload):
    body = client.post("/api/profile", json=profile_payload).get_json()
    assert body["calories"] == 2800
    assert body["program_name"] == "Muscle Gain (MG)"
    assert body["adherence"] == 85


def test_profile_endpoint_reports_the_failing_field(client, profile_payload):
    profile_payload["age"] = 7
    response = client.post("/api/profile", json=profile_payload)
    assert response.status_code == 400
    assert response.get_json() == {
        "error": "ValidationError", "message": "'age' must be between 10 and 100", "field": "age",
    }
