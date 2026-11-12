"""Client roster, CSV export and the endpoints/pages built on them."""

from __future__ import annotations

import csv
import io

import pytest

from aceest.errors import ConflictError
from aceest.exports import CSV_COLUMNS, clients_to_csv
from aceest.roster import ClientRoster


def test_roster_returns_copies():
    roster = ClientRoster()
    roster.add({"name": "Ravi"})
    roster.all()[0]["name"] = "changed"
    assert roster.all()[0]["name"] == "Ravi"
    assert len(roster) == 1


def test_roster_rejects_a_second_client_with_the_same_name():
    roster = ClientRoster()
    roster.add({"name": "Ravi Kumar"})
    with pytest.raises(ConflictError):
        roster.add({"name": "ravi kumar"})


def test_duplicate_client_is_a_409(client, profile_payload):
    assert client.post("/api/clients", json=profile_payload).status_code == 201
    response = client.post("/api/clients", json=profile_payload)
    assert response.status_code == 409
    assert response.get_json()["field"] == "name"
    assert client.get("/api/clients").get_json()["count"] == 1


def test_duplicate_from_the_dashboard_shows_the_reason(client):
    form = {"name": "Meera Nair", "age": "28", "weight_kg": "58", "program": "FL"}
    client.post("/profile", data=form)
    response = client.post("/profile", data=form)
    assert response.status_code == 409
    assert "already exists" in response.get_data(as_text=True)


def test_csv_has_the_desktop_columns_and_one_row_per_client(profile_payload, client):
    client.post("/api/clients", json=profile_payload)
    rows = list(csv.reader(io.StringIO(client.get("/api/clients/export.csv").get_data(as_text=True))))
    assert tuple(rows[0]) == CSV_COLUMNS
    assert rows[1] == ["Ravi Kumar", "32", "80.0", "MG", "85", "", "2800"]


def test_csv_neutralises_formula_like_notes():
    text = clients_to_csv([{
        "name": "Ravi Kumar", "age": 32, "weight_kg": 80.0, "program": "MG",
        "adherence": 85, "notes": "=HYPERLINK(1)", "calories": 2800,
    }])
    assert "'=HYPERLINK" in text


def test_export_is_served_as_a_csv_download(client):
    response = client.get("/api/clients/export.csv")
    assert response.mimetype == "text/csv"
    assert "attachment" in response.headers["Content-Disposition"]


def test_add_and_list_clients(client, profile_payload):
    created = client.post("/api/clients", json=profile_payload)
    assert created.status_code == 201
    assert created.get_json()["calories"] == 2800

    listing = client.get("/api/clients").get_json()
    assert listing["count"] == 1
    assert listing["clients"][0]["name"] == "Ravi Kumar"


def test_invalid_client_is_not_added(client, profile_payload):
    profile_payload["program"] = "ZZ"
    assert client.post("/api/clients", json=profile_payload).status_code == 400
    assert client.get("/api/clients").get_json()["count"] == 0


def test_each_app_has_its_own_roster(app, profile_payload):
    from aceest import create_app

    other = create_app("testing", overrides={"WTF_CSRF_ENABLED": False})
    app.test_client().post("/api/clients", json=profile_payload)
    assert other.test_client().get("/api/clients").get_json()["count"] == 0


def test_saving_from_the_dashboard_lists_and_charts_the_client(client):
    page = client.post("/profile", data={
        "name": "Meera Nair", "age": "28", "weight_kg": "58", "program": "FL",
        "adherence": "70", "notes": "prefers mornings",
    }).get_data(as_text=True)
    assert "<td>Meera Nair</td>" in page
    assert "prefers mornings" in page
    assert 'style="width: 70%"' in page
