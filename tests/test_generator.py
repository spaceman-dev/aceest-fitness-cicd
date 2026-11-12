"""Weekly program generator and the PDF report (3.1.2)."""

from __future__ import annotations

from datetime import date

import pytest

from aceest import services
from aceest.errors import ValidationError
from aceest.generator import EXERCISE_POOLS, LEVELS, focus_for, generate_program
from aceest.reports import client_report


@pytest.mark.parametrize(("program", "focus"), [("FL3", "Conditioning"), ("FL5", "Conditioning"),
                                                ("MG", "Hypertrophy"), ("BG", "Full Body")])
def test_focus_follows_the_program(program, focus):
    assert focus_for(program) == focus


@pytest.mark.parametrize("level", list(LEVELS))
def test_plan_respects_the_experience_level(level):
    rules = LEVELS[level]
    plan = generate_program("Ravi Kumar", "MG", level.upper(), "2026-W46")
    assert plan["days"] == rules["days"]
    per_day = 3 if rules["days"] < 4 else 4
    assert len(plan["sessions"]) == rules["days"] * per_day
    for row in plan["sessions"]:
        assert row["exercise"] in EXERCISE_POOLS["Hypertrophy"]
        assert rules["sets"][0] <= row["sets"] <= rules["sets"][1]
        assert rules["reps"][0] <= row["reps"] <= rules["reps"][1]


def test_same_week_same_plan_next_week_new_plan():
    first = generate_program("Ravi Kumar", "FL3", "advanced", "2026-W46")
    assert first == generate_program("Ravi Kumar", "FL3", "advanced", "2026-W46")
    assert first["sessions"] != generate_program("Ravi Kumar", "FL3", "advanced", "2026-W47")["sessions"]


def test_no_exercise_repeats_within_a_day():
    plan = generate_program("Meera Nair", "BG", "intermediate", "2026-W46")
    for day in {row["day"] for row in plan["sessions"]}:
        names = [row["exercise"] for row in plan["sessions"] if row["day"] == day]
        assert len(names) == len(set(names))


@pytest.mark.parametrize("level", ["expert", "", None])
def test_unknown_level_is_rejected(level):
    with pytest.raises(ValidationError):
        generate_program("Ravi Kumar", "MG", level, "2026-W46")


def test_program_api(client, enrolled):
    body = client.get("/api/clients/Ravi Kumar/program?experience=beginner").get_json()
    assert (body["focus"], body["days"]) == ("Hypertrophy", 3)
    assert client.get("/api/clients/Ravi Kumar/program?experience=pro").status_code == 400


def test_program_on_the_client_page(client, enrolled):
    page = client.get("/clients/Ravi Kumar?experience=advanced").get_data(as_text=True)
    assert "Hypertrophy focus &middot; 5 days" in page
    assert "<td>Friday</td>" in page
    bad = client.get("/clients/Ravi Kumar?experience=pro").get_data(as_text=True)
    assert "&#39;experience&#39; must be beginner" in bad


@pytest.mark.parametrize(("end", "status", "days"), [
    (None, "Not set", None),
    ("2026-11-11", "Expired", -1),
    ("2026-11-12", "Expiring soon", 0),
    ("2026-11-26", "Expiring soon", 14),
    ("2026-11-27", "Active", 15),
])
def test_membership_status(end, status, days):
    assert services.membership_status(end, date(2026, 11, 12)) == {
        "membership_status": status, "days_left": days}


def test_membership_end_is_validated(profile_payload):
    assert services.build_profile({**profile_payload, "membership_end": "2027-01-31"})["membership_end"] == "2027-01-31"
    with pytest.raises(ValidationError) as excinfo:
        services.build_profile({**profile_payload, "membership_end": "31/01/2027"})
    assert excinfo.value.field == "membership_end"


def test_membership_shows_on_roster_and_client_page(client, profile_payload):
    client.post("/api/clients", json={**profile_payload, "membership_end": "2020-01-01"})
    assert "<td>Expired</td>" in client.get("/").get_data(as_text=True)
    assert "Status    : Expired" in client.get("/clients/Ravi Kumar").get_data(as_text=True)


def test_report_is_a_pdf():
    pdf = client_report({"name": "Ravi Kumar", "age": 32, "weight_kg": 80, "program_name": "MG",
                         "calories": 2800, "membership_status": "Active", "notes": "ünïcode ✓"},
                        {"weeks_logged": 2, "average_adherence": 85.0},
                        [{"date": "2026-11-10", "workout_type": "Strength", "duration_min": 60,
                          "notes": "heavy día ✓"}], "2026-11-12")
    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 1000


def test_report_downloads(client, enrolled):
    response = client.get("/clients/Ravi Kumar/report.pdf")
    assert response.mimetype == "application/pdf"
    assert response.headers["Content-Disposition"] == "attachment; filename=Ravi_Kumar_report.pdf"
    assert response.data.startswith(b"%PDF")
    assert client.get("/api/clients/Ravi Kumar/report.pdf").data.startswith(b"%PDF")
