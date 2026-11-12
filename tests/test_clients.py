"""Client records and weekly progress, stored in SQLite."""

from __future__ import annotations

import csv
import io
import sqlite3
from contextlib import closing

import pytest

from aceest import db
from aceest.exports import CSV_COLUMNS, clients_to_csv


class TestSchema:
    def test_migrations_are_recorded_and_idempotent(self, tmp_path):
        with closing(db.connect(str(tmp_path / "m.db"))) as connection:
            latest = db.MIGRATIONS[-1][0]
            assert db.migrate(connection) == latest
            assert db.migrate(connection) == latest
            versions = [row[0] for row in connection.execute("SELECT version FROM schema_version")]
        assert versions == [number for number, _ in db.MIGRATIONS]

    def test_failed_migration_leaves_no_half_applied_schema(self, tmp_path, monkeypatch):
        monkeypatch.setattr(db, "MIGRATIONS", [(1, ["CREATE TABLE ok (id INTEGER)", "NOT SQL"])])
        with closing(db.connect(str(tmp_path / "bad.db"))) as connection:
            with pytest.raises(sqlite3.OperationalError):
                db.migrate(connection)
            tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master")}
        assert "ok" not in tables

    def test_upgrade_from_2_0_1_keeps_the_latest_duplicate_week(self, tmp_path, monkeypatch):
        with closing(db.connect(str(tmp_path / "old.db"))) as connection:
            monkeypatch.setattr(db, "MIGRATIONS", db.MIGRATIONS[:1])
            db.migrate(connection)
            connection.execute("INSERT INTO clients (name, age, weight_kg, program, calories) "
                               "VALUES ('Ravi Kumar', 32, 80, 'MG', 2800)")
            for adherence in (50, 70, 90):
                connection.execute("INSERT INTO progress (client_id, week, adherence) "
                                   "VALUES (1, '2026-W45', ?)", (adherence,))
            connection.commit()
            monkeypatch.undo()

            assert db.migrate(connection) == db.MIGRATIONS[-1][0]
            rows = connection.execute("SELECT week, adherence FROM progress").fetchall()
        assert [tuple(row) for row in rows] == [("2026-W45", 90)]

    def test_database_runs_in_wal_mode(self, app):
        with app.app_context():
            assert db.get_db().execute("PRAGMA journal_mode").fetchone()[0] == "wal"

    def test_names_are_unique_regardless_of_case(self, app, profile_payload):
        with app.app_context():
            db.insert_client({**profile_payload, "calories": 2800, "notes": "", "weight_kg": 80.0})
            with pytest.raises(sqlite3.IntegrityError):
                db.insert_client({**profile_payload, "name": "RAVI KUMAR", "calories": 2800,
                                  "notes": "", "weight_kg": 80.0})


class TestClientApi:
    def test_create_and_load(self, client, enrolled):
        assert enrolled["calories"] == 2800
        body = client.get("/api/clients/ravi kumar").get_json()
        assert body["name"] == "Ravi Kumar"
        assert body["progress"] == []

    def test_listing(self, client, enrolled):
        listing = client.get("/api/clients").get_json()
        assert listing["count"] == 1
        assert listing["clients"][0]["program"] == "MG"

    def test_duplicate_name_is_a_409(self, client, enrolled, profile_payload):
        response = client.post("/api/clients", json=profile_payload)
        assert response.status_code == 409
        assert response.get_json()["field"] == "name"

    def test_update_recomputes_calories(self, client, enrolled):
        response = client.put("/api/clients/Ravi Kumar",
                              json={"age": 33, "weight_kg": 70, "program": "FL"})
        assert response.status_code == 200
        assert response.get_json()["calories"] == 1540

    def test_update_cannot_take_another_clients_name(self, client, enrolled, profile_payload):
        client.post("/api/clients", json={**profile_payload, "name": "Meera Nair"})
        response = client.put("/api/clients/Meera Nair", json={**profile_payload})
        assert response.status_code == 409

    def test_unknown_client_is_a_404(self, client):
        assert client.get("/api/clients/Nobody").status_code == 404
        assert client.put("/api/clients/Nobody", json={}).status_code == 404

    def test_data_survives_a_new_app_on_the_same_file(self, app, enrolled, profile_payload):
        from aceest import create_app

        again = create_app("testing", overrides={"DATABASE": app.config["DATABASE"]})
        assert again.test_client().get("/api/clients/Ravi Kumar").status_code == 200


class TestProgressApi:
    def test_log_and_read_progress(self, client, enrolled):
        logged = client.post("/api/clients/Ravi Kumar/progress",
                             json={"week": "2026-W45", "adherence": 90})
        assert logged.status_code == 201
        assert logged.get_json()["week"] == "2026-W45"
        entries = client.get("/api/clients/Ravi Kumar/progress").get_json()["entries"]
        assert [(e["week"], e["adherence"]) for e in entries] == [("2026-W45", 90)]

    def test_week_defaults_to_the_current_iso_week(self, client, enrolled):
        from aceest.services import current_week

        logged = client.post("/api/clients/Ravi Kumar/progress", json={"adherence": 75})
        assert logged.get_json()["week"] == current_week()

    @pytest.mark.parametrize(("payload", "field"), [
        ({"week": "2026-W60", "adherence": 80}, "week"),
        ({"week": "last week", "adherence": 80}, "week"),
        ({"adherence": 140}, "adherence"),
        ({}, "adherence"),
    ])
    def test_bad_progress_is_rejected(self, client, enrolled, payload, field):
        response = client.post("/api/clients/Ravi Kumar/progress", json=payload)
        assert response.status_code == 400
        assert response.get_json()["field"] == field

    def test_logging_the_same_week_again_replaces_it(self, client, enrolled):
        client.post("/api/clients/Ravi Kumar/progress", json={"week": "2026-W45", "adherence": 60})
        client.post("/api/clients/Ravi Kumar/progress", json={"week": "2026-W45", "adherence": 95})
        entries = client.get("/api/clients/Ravi Kumar/progress").get_json()["entries"]
        assert [(e["week"], e["adherence"]) for e in entries] == [("2026-W45", 95)]

    def test_entries_come_back_in_week_order(self, client, enrolled):
        for week in ("2026-W46", "2026-W44", "2026-W45"):
            client.post("/api/clients/Ravi Kumar/progress", json={"week": week, "adherence": 80})
        entries = client.get("/api/clients/Ravi Kumar/progress").get_json()["entries"]
        assert [e["week"] for e in entries] == ["2026-W44", "2026-W45", "2026-W46"]

    def test_progress_for_an_unknown_client_is_a_404(self, client):
        response = client.post("/api/clients/Ghost/progress", json={"adherence": 80})
        assert response.status_code == 404


class TestCsvExport:
    def test_columns_and_rows(self, client, enrolled):
        text = client.get("/api/clients/export.csv").get_data(as_text=True)
        rows = list(csv.reader(io.StringIO(text)))
        assert tuple(rows[0]) == CSV_COLUMNS
        assert rows[1] == ["Ravi Kumar", "32", "80.0", "MG", "85", "", "2800"]

    def test_formula_like_text_is_quoted(self):
        text = clients_to_csv([{
            "name": "Ravi Kumar", "age": 32, "weight_kg": 80.0, "program": "MG",
            "adherence": 85, "notes": "=HYPERLINK(1)", "calories": 2800,
        }])
        assert "'=HYPERLINK" in text

    def test_served_as_a_download(self, client):
        response = client.get("/api/clients/export.csv")
        assert response.mimetype == "text/csv"
        assert "attachment" in response.headers["Content-Disposition"]


class TestPages:
    def test_save_client_creates_then_updates(self, client):
        form = {"name": "Meera Nair", "age": "28", "weight_kg": "58", "program": "FL", "adherence": "70"}
        first = client.post("/profile", data=form).get_data(as_text=True)
        assert "Client Meera Nair saved successfully" in first
        second = client.post("/profile", data={**form, "weight_kg": "60"}).get_data(as_text=True)
        assert "Client Meera Nair updated" in second
        assert client.get("/api/clients/Meera Nair").get_json()["calories"] == 1320

    def test_client_page_shows_the_profile_block(self, client, enrolled):
        page = client.get("/clients/Ravi Kumar").get_data(as_text=True)
        assert "CLIENT PROFILE" in page
        assert "Calories : 2800 kcal/day" in page

    def test_saving_progress_from_the_page(self, client, enrolled):
        response = client.post("/clients/Ravi Kumar/progress",
                               data={"week": "2026-W44", "adherence": "88"}, follow_redirects=True)
        page = response.get_data(as_text=True)
        assert "Week 2026-W44 recorded at 88%" in page
        assert "<td>2026-W44</td><td>88%</td>" in page

    def test_bad_progress_from_the_page_is_flashed(self, client, enrolled):
        response = client.post("/clients/Ravi Kumar/progress",
                               data={"week": "soon", "adherence": "88"}, follow_redirects=True)
        assert "must look like 2026-W46" in response.get_data(as_text=True)

    def test_unknown_client_page_is_a_404(self, client):
        assert client.get("/clients/Nobody").status_code == 404
