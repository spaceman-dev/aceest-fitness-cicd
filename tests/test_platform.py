"""3.0 platform pieces: stats, health checks, metrics and fault injection."""

from __future__ import annotations

import pytest

from aceest import __version__, create_app
from aceest.observability import RequestMetrics


def test_stats_aggregate_the_roster(client, profile_payload):
    client.post("/api/clients", json=profile_payload)
    client.post("/api/clients", json={**profile_payload, "name": "Meera Nair", "weight_kg": 60,
                                      "program": "FL3"})
    body = client.get("/api/stats").get_json()
    assert body["total_clients"] == 2
    assert body["clients_by_program"] == {"FL3": 1, "MG": 1}
    assert body["average_calorie_target"] == (2800 + 1320) / 2
    assert body["capacity_used_pct"] == 1.3
    assert body["site_metrics"]["capacity_users"] == 150


def test_stats_on_an_empty_gym(client):
    body = client.get("/api/stats").get_json()
    assert (body["total_clients"], body["average_calorie_target"]) == (0, 0.0)


def test_dashboard_overview_cards(client, enrolled):
    page = client.get("/").get_data(as_text=True)
    assert "Active clients" in page
    assert "0.7%" in page  # 1 of 150


def test_health_reports_the_database_check(client):
    body = client.get("/api/health").get_json()
    assert body["checks"] == {"database": "ok"}


def test_health_is_503_when_the_database_is_unreachable(app, tmp_path):
    app.config["DATABASE"] = str(tmp_path)  # a directory cannot be opened as a database
    response = app.test_client().get("/api/health")
    assert response.status_code == 503
    assert response.get_json()["checks"]["database"] == "unavailable"


def test_metrics_count_requests_by_route(client, enrolled):
    client.get("/api/clients/Ravi Kumar")
    client.get("/api/clients/Ravi Kumar")
    text = client.get("/metrics").get_data(as_text=True)
    assert f'aceest_build_info{{version="{__version__}",track="test"}} 1' in text
    assert 'aceest_http_requests_total{method="GET",route="/api/clients/<name>",status="200"} 2' in text
    assert "aceest_http_request_duration_seconds_count" in text


def test_metric_labels_are_escaped():
    metrics = RequestMetrics()
    metrics.observe("GET", '/odd"route', 200, 0.01)
    assert '/odd\\"route' in metrics.render("1.0.0", 'tr"ack')


def _faulty(tmp_path, fault):
    return create_app("testing", overrides={"FAULT": fault, "DATABASE": str(tmp_path / "f.db")})


def test_unhealthy_fault_fails_the_health_check_only(tmp_path):
    client = _faulty(tmp_path, "unhealthy").test_client()
    assert client.get("/api/health").status_code == 503
    assert client.get("/api/programs").status_code == 200


def test_errors_fault_breaks_the_api_but_not_health(tmp_path):
    client = _faulty(tmp_path, "errors").test_client()
    assert client.get("/api/health").status_code == 200
    assert client.get("/api/programs").status_code == 500
    assert client.get("/login").status_code == 200


def test_unknown_fault_is_refused(tmp_path):
    with pytest.raises(ValueError):
        _faulty(tmp_path, "chaos-monkey")
