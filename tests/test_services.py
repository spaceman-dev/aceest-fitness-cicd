"""Unit tests for the business rules in aceest.services."""

from __future__ import annotations

import pytest

from aceest import services
from aceest.errors import ValidationError


@pytest.mark.parametrize(("weight", "program", "expected"), [
    (80, "MG", 2800),
    (70, "FL", 1540),
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
        "program_name": "Muscle Gain (MG)", "calories": 2800, "adherence": 85,
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
