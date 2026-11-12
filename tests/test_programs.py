"""Program catalogue rules."""

from __future__ import annotations

import pytest

from aceest.programs import PROGRAMS, SITE_METRICS, get_program, list_programs


def test_catalogue_has_the_three_launch_programs():
    assert set(PROGRAMS) == {"FL", "MG", "BG"}
    assert [p["code"] for p in list_programs()] == ["FL", "MG", "BG"]


@pytest.mark.parametrize("code", ["FL", "MG", "BG"])
def test_every_program_has_a_plan_and_a_colour(code):
    program = PROGRAMS[code]
    assert program["workout"].strip()
    assert program["diet"].strip()
    assert program["colour"].startswith("#")


def test_lookup_ignores_case_and_spaces():
    assert get_program(" mg ")["code"] == "MG"


@pytest.mark.parametrize("bad", ["XX", "", None, 42])
def test_unknown_or_invalid_codes_return_none(bad):
    assert get_program(bad) is None


def test_site_metrics_match_the_brief():
    assert SITE_METRICS == {
        "capacity_users": 150,
        "area_sq_ft": 10000,
        "break_even_members": 250,
    }
