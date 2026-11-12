"""Training program catalogue (ported from Aceestver-1.0)."""

from __future__ import annotations

from typing import Any

PROGRAMS: dict[str, dict[str, Any]] = {
    "FL": {
        "code": "FL",
        "name": "Fat Loss (FL)",
        "workout": (
            "Mon: 5x5 Back Squat + AMRAP\n"
            "Tue: EMOM 20min Assault Bike\n"
            "Wed: Bench Press + 21-15-9\n"
            "Thu: 10RFT Deadlifts/Box Jumps\n"
            "Fri: 30min Active Recovery"
        ),
        "diet": (
            "B: 3 Egg Whites + Oats Idli\n"
            "L: Grilled Chicken + Brown Rice\n"
            "D: Fish Curry + Millet Roti\n"
            "Target: 2,000 kcal"
        ),
        "colour": "#e74c3c",
    },
    "MG": {
        "code": "MG",
        "name": "Muscle Gain (MG)",
        "workout": (
            "Mon: Squat 5x5\n"
            "Tue: Bench 5x5\n"
            "Wed: Deadlift 4x6\n"
            "Thu: Front Squat 4x8\n"
            "Fri: Incline Press 4x10\n"
            "Sat: Barbell Rows 4x10"
        ),
        "diet": (
            "B: 4 Eggs + PB Oats\n"
            "L: Chicken Biryani (250g Chicken)\n"
            "D: Mutton Curry + Jeera Rice\n"
            "Target: 3,200 kcal"
        ),
        "colour": "#2ecc71",
    },
    "BG": {
        "code": "BG",
        "name": "Beginner (BG)",
        "workout": (
            "Circuit Training: Air Squats, Ring Rows, Push-ups.\n"
            "Focus: Technique Mastery & Form (90% Threshold)"
        ),
        "diet": (
            "Balanced Tamil Meals: Idli-Sambar, Rice-Dal, Chapati.\n"
            "Protein: 120g/day"
        ),
        "colour": "#3498db",
    },
}

# Reference figures for the site, shown on the dashboard.
SITE_METRICS = {
    "capacity_users": 150,
    "area_sq_ft": 10000,
    "break_even_members": 250,
}


def list_programs() -> list[dict[str, Any]]:
    return list(PROGRAMS.values())


def get_program(code: Any) -> dict[str, Any] | None:
    """Look a program up by code, ignoring case and surrounding spaces."""
    if not isinstance(code, str):
        return None
    return PROGRAMS.get(code.strip().upper())
