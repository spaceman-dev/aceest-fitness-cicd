"""2.2.4 tracking: height/BMI, goals, workouts with exercises, body metrics."""

from __future__ import annotations

from contextlib import closing

from aceest import db


def test_client_with_height_reports_bmi_and_goals(client, profile_payload):
    body = client.post("/api/clients", json={**profile_payload, "height_cm": 175,
                                             "target_weight_kg": 76, "target_adherence": 90}).get_json()
    assert (body["bmi"], body["category"]) == (26.1, "Overweight")
    assert body["target_weight_kg"] == 76.0
    assert body["program_notes"] == "Push/Pull/Legs hypertrophy"


def test_log_workout_with_exercises(client, enrolled):
    response = client.post("/api/clients/Ravi Kumar/workouts", json={
        "date": "2026-11-10", "workout_type": "Strength", "duration_min": 60, "notes": "felt strong",
        "exercises": [{"name": "Back Squat", "sets": 5, "reps": 5, "weight_kg": 100},
                      {"name": "Plank", "sets": 3, "reps": 1}],
    })
    assert response.status_code == 201
    assert [e["name"] for e in response.get_json()["exercises"]] == ["Back Squat", "Plank"]

    history = client.get("/api/clients/Ravi Kumar/workouts").get_json()
    assert history["count"] == 1
    assert history["total_minutes"] == 60


def test_bad_workout_is_rejected(client, enrolled):
    response = client.post("/api/clients/Ravi Kumar/workouts", json={"workout_type": "Nap", "duration_min": 20})
    assert response.status_code == 400


def test_metrics_and_weight_chart(client, enrolled):
    for day, weight in (("2026-11-01", 82), ("2026-11-08", 80.5)):
        assert client.post("/api/clients/Ravi Kumar/metrics",
                           json={"date": day, "weight_kg": weight, "waist_cm": 90}).status_code == 201
    entries = client.get("/api/clients/Ravi Kumar/metrics").get_json()["entries"]
    assert [e["weight_kg"] for e in entries] == [82.0, 80.5]

    chart = client.get("/api/clients/Ravi Kumar/metrics/chart.svg")
    assert chart.mimetype == "image/svg+xml"
    assert "Weight trend - Ravi Kumar" in chart.get_data(as_text=True)


def test_client_detail_includes_tracking_data(client, enrolled):
    client.post("/api/clients/Ravi Kumar/progress", json={"week": "2026-W45", "adherence": 70})
    client.post("/api/clients/Ravi Kumar/progress", json={"week": "2026-W46", "adherence": 90})
    client.post("/api/clients/Ravi Kumar/metrics", json={"date": "2026-11-08", "bodyfat_pct": 18})
    body = client.get("/api/clients/Ravi Kumar").get_json()
    assert body["progress_summary"]["trend"] == "improving"
    assert body["last_metrics"]["bodyfat_pct"] == 18.0
    assert body["workouts"] == []


def test_deleting_a_client_removes_their_records(app, client, enrolled):
    client.post("/api/clients/Ravi Kumar/workouts", json={
        "workout_type": "Strength", "duration_min": 30, "exercises": [{"name": "Row", "sets": 3, "reps": 8}]})
    with app.app_context():
        connection = db.get_db()
        connection.execute("DELETE FROM clients")
        connection.commit()
        assert connection.execute("SELECT COUNT(*) FROM exercises").fetchone()[0] == 0


def test_upgrade_moves_old_fat_loss_clients_to_fl3(tmp_path, monkeypatch):
    with closing(db.connect(str(tmp_path / "old.db"))) as connection:
        monkeypatch.setattr(db, "MIGRATIONS", db.MIGRATIONS[:2])
        db.migrate(connection)
        connection.execute("INSERT INTO clients (name, age, weight_kg, program, calories) "
                           "VALUES ('Meera Nair', 28, 58, 'FL', 1276)")
        connection.commit()
        monkeypatch.undo()
        db.migrate(connection)
        row = connection.execute("SELECT program, height_cm FROM clients").fetchone()
    assert tuple(row) == ("FL3", None)


class TestPages:
    def test_workout_form(self, client, enrolled):
        page = client.post("/clients/Ravi Kumar/workouts", data={
            "date": "2026-11-10", "workout_type": "Mobility", "duration_min": "30",
            "exercise_name": "Hip flow", "exercise_sets": "2", "exercise_reps": "10",
            "exercise_weight_kg": "0",
        }, follow_redirects=True).get_data(as_text=True)
        assert "Mobility session on 2026-11-10 logged" in page
        assert "Hip flow 2x10" in page

    def test_workout_form_without_exercise(self, client, enrolled):
        page = client.post("/clients/Ravi Kumar/workouts", data={
            "workout_type": "Conditioning", "duration_min": "20", "exercise_name": "",
        }, follow_redirects=True).get_data(as_text=True)
        assert "Conditioning session on" in page

    def test_bad_workout_form_is_flashed(self, client, enrolled):
        page = client.post("/clients/Ravi Kumar/workouts", data={"workout_type": "Strength",
                                                                 "duration_min": "999"},
                           follow_redirects=True).get_data(as_text=True)
        assert "&#39;duration_min&#39; must be between 1 and 480" in page

    def test_metrics_form(self, client, enrolled):
        page = client.post("/clients/Ravi Kumar/metrics", data={
            "date": "2026-11-09", "weight_kg": "79.5", "waist_cm": "", "bodyfat_pct": "",
        }, follow_redirects=True).get_data(as_text=True)
        assert "Body metrics for 2026-11-09 logged" in page
        assert "2026-11-09 | 79.5 kg" in page

    def test_bad_metrics_form_is_flashed(self, client, enrolled):
        page = client.post("/clients/Ravi Kumar/metrics", data={"weight_kg": "", "waist_cm": ""},
                           follow_redirects=True).get_data(as_text=True)
        assert "give at least one of" in page

    def test_bmi_card(self, client, profile_payload):
        client.post("/api/clients", json={**profile_payload, "height_cm": 180})
        page = client.get("/clients/Ravi Kumar").get_data(as_text=True)
        assert "BMI 24.7 (Normal)" in page

    def test_bmi_card_without_height(self, client, enrolled):
        assert "Add the client's height" in client.get("/clients/Ravi Kumar").get_data(as_text=True)
