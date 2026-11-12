"""Unit tests for the business rules in aceest.services."""

from __future__ import annotations

import pytest

from aceest import services
from aceest.errors import ValidationError


@pytest.mark.parametrize(("weight", "program", "expected"), [
    (80, "MG", 2800),
    (70, "FL3", 1540),
    (70, "FL5", 1680),
    (60, "BG", 1560),
    ("72.5", "fl", 1595),
])
def test_calories_are_weight_times_program_factor(weight, program, expected):
    assert services.calculate_calories(weight, program) == expected


def test_calories_are_truncated_not_rounded():
    # weight is kept to 0.1 kg first: 72.56 -> 72.6, and 72.6 x 22 = 1597.2 -> 1597
    assert services.calculate_calories(72.56, "FL") == 1597


@pytest.mark.parametrize("weight", [0, 24.9, 300.1, "heavy", None, True])
def test_weight_outside_range_or_not_numeric_is_rejected(weight):
    with pytest.raises(ValidationError) as excinfo:
        services.calculate_calories(weight, "MG")
    assert excinfo.value.field == "weight_kg"


def test_unknown_program_is_rejected():
    with pytest.raises(ValidationError) as excinfo:
        services.calculate_calories(80, "CROSSFIT")
    assert excinfo.value.field == "program"


@pytest.mark.parametrize("name", ["Ravi Kumar", "O'Neil", "Anne-Marie", "  Ravi   Kumar "])
def test_valid_names(name):
    assert services.validate_name(name) == " ".join(name.split())


@pytest.mark.parametrize("name", ["R", "1Ravi", "Ravi<script>", "", 42])
def test_invalid_names(name):
    with pytest.raises(ValidationError):
        services.validate_name(name)


@pytest.mark.parametrize(("age", "ok"), [(10, True), (100, True), (9, False), (101, False), (30.5, False)])
def test_age_limits(age, ok):
    if ok:
        assert services.validate_age(age) == age
    else:
        with pytest.raises(ValidationError):
            services.validate_age(age)


@pytest.mark.parametrize(("value", "ok"), [(0, True), (100, True), ("85", True), (-1, False), (101, False)])
def test_adherence_limits(value, ok):
    if ok:
        assert services.validate_adherence(value) == int(value)
    else:
        with pytest.raises(ValidationError):
            services.validate_adherence(value)


def test_build_profile_derives_calories(profile_payload):
    profile = services.build_profile(profile_payload)
    assert profile == {
        "name": "Ravi Kumar", "age": 32, "weight_kg": 80.0, "program": "MG",
        "program_name": "Muscle Gain (MG) - PPL", "calories": 2800, "adherence": 85, "notes": "",
        "height_cm": None, "target_weight_kg": None, "target_adherence": None,
        "membership_end": None,
    }


def test_build_profile_defaults_adherence_to_zero(profile_payload):
    del profile_payload["adherence"]
    assert services.build_profile(profile_payload)["adherence"] == 0


@pytest.mark.parametrize("missing", ["name", "age", "weight_kg", "program"])
def test_build_profile_requires_every_field(profile_payload, missing):
    profile_payload[missing] = ""
    with pytest.raises(ValidationError) as excinfo:
        services.build_profile(profile_payload)
    assert excinfo.value.field == missing


def test_build_profile_needs_a_mapping():
    with pytest.raises(ValidationError):
        services.build_profile(["not", "a", "dict"])


def test_notes_are_trimmed_and_limited():
    assert services.validate_notes("  knee rehab  ") == "knee rehab"
    assert services.validate_notes(None) == ""
    with pytest.raises(ValidationError):
        services.validate_notes("x" * 281)
    with pytest.raises(ValidationError):
        services.validate_notes(42)


def test_current_week_is_iso():
    from datetime import date

    assert services.current_week(date(2026, 11, 12)) == "2026-W46"


@pytest.mark.parametrize("week", ["2026-W01", "2026-W53", " 2026-W46 "])
def test_valid_weeks(week):
    assert services.validate_week(week) == week.strip()


@pytest.mark.parametrize("week", ["2026-W00", "2026-W54", "W46", 46])
def test_invalid_weeks(week):
    with pytest.raises(ValidationError):
        services.validate_week(week)


@pytest.mark.parametrize(("weight", "height", "bmi", "category"), [
    (50, 175, 16.3, "Underweight"),
    (70, 175, 22.9, "Normal"),
    (80, 175, 26.1, "Overweight"),
    (100, 175, 32.7, "Obese"),
])
def test_bmi_bands(weight, height, bmi, category):
    report = services.bmi_report(weight, height)
    assert (report["bmi"], report["category"]) == (bmi, category)
    assert report["risk"]


@pytest.mark.parametrize("bmi,category", [(18.49, "Underweight"), (18.5, "Normal"),
                                          (24.99, "Normal"), (25, "Overweight"), (30, "Obese")])
def test_bmi_band_edges(bmi, category):
    assert services.classify_bmi(bmi)["category"] == category


@pytest.mark.parametrize("height", [89, 251, "tall"])
def test_height_limits(height):
    with pytest.raises(ValidationError):
        services.validate_height_cm(height)


def test_profile_goals_and_height_are_optional_but_validated(profile_payload):
    profile = services.build_profile({**profile_payload, "height_cm": "180",
                                      "target_weight_kg": 75, "target_adherence": 90})
    assert (profile["height_cm"], profile["target_weight_kg"], profile["target_adherence"]) == (180.0, 75.0, 90)
    with pytest.raises(ValidationError):
        services.build_profile({**profile_payload, "target_adherence": 120})


def test_describe_client_adds_program_details_and_bmi():
    described = services.describe_client({"program": "FL", "weight_kg": 80.0, "height_cm": 180.0})
    assert described["program_name"] == "Fat Loss (FL) - 3 day"
    assert described["bmi"] == 24.7
    assert "bmi" not in services.describe_client({"program": "MG", "weight_kg": 80.0, "height_cm": None})


def test_workout_validation():
    workout = services.validate_workout({
        "date": "2026-11-10", "workout_type": "strength", "duration_min": "60",
        "exercises": [{"name": "Back Squat", "sets": 5, "reps": 5, "weight_kg": 100}],
    })
    assert workout["workout_type"] == "Strength"
    assert workout["exercises"] == [{"name": "Back Squat", "sets": 5, "reps": 5, "weight_kg": 100.0}]


@pytest.mark.parametrize(("payload", "field"), [
    ({"workout_type": "Yoga", "duration_min": 30}, "workout_type"),
    ({"workout_type": "Strength", "duration_min": 0}, "duration_min"),
    ({"workout_type": "Strength", "duration_min": 30, "date": "12/11/2026"}, "date"),
    ({"workout_type": "Strength", "duration_min": 30, "exercises": "squats"}, "exercises"),
    ({"workout_type": "Strength", "duration_min": 30, "exercises": ["squats"]}, "exercises"),
    ({"workout_type": "Strength", "duration_min": 30, "exercises": [{"name": "", "sets": 1, "reps": 1}]}, "name"),
    ({"workout_type": "Strength", "duration_min": 30, "exercises": [{"name": "x" * 61, "sets": 1, "reps": 1}]}, "name"),
    ({"workout_type": "Strength", "duration_min": 30, "exercises": [{"name": "Row", "sets": 30, "reps": 1}]}, "sets"),
])
def test_bad_workouts_are_rejected(payload, field):
    with pytest.raises(ValidationError) as excinfo:
        services.validate_workout(payload)
    assert excinfo.value.field == field


def test_metrics_need_at_least_one_measurement():
    assert services.validate_metrics({"waist_cm": 82})["waist_cm"] == 82.0
    with pytest.raises(ValidationError):
        services.validate_metrics({"date": "2026-11-10"})
    with pytest.raises(ValidationError):
        services.validate_metrics({"bodyfat_pct": 90})


def test_adherence_summary():
    assert services.summarise_adherence([])["trend"] == "no data"
    rising = services.summarise_adherence([{"adherence": 60}, {"adherence": 80}])
    assert rising == {"weeks_logged": 2, "average_adherence": 70.0, "latest_adherence": 80,
                      "trend": "improving"}
    assert services.summarise_adherence([{"adherence": 80}, {"adherence": 60}])["trend"] == "declining"
    assert services.summarise_adherence([{"adherence": 80}])["trend"] == "steady"
