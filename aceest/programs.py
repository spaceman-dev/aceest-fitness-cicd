"""Training program catalogue (plans as of Aceestver-1.1).

``calorie_factor`` is kcal per kg of body weight per day.
"""

from __future__ import annotations

from typing import Any

PROGRAMS: dict[str, dict[str, Any]] = {
    "FL": {
        "code": "FL",
        "name": "Fat Loss (FL)",
        "workout": (
            "Mon: Back Squat 5x5 + Core\n"
            "Tue: EMOM 20min Assault Bike\n"
            "Wed: Bench Press + 21-15-9\n"
            "Thu: Deadlift + Box Jumps\n"
            "Fri: Zone 2 Cardio 30min"
        ),
        "diet": (
            "Breakfast: Egg Whites + Oats\n"
            "Lunch: Grilled Chicken + Brown Rice\n"
            "Dinner: Fish Curry + Millet Roti\n"
            "Target: ~2000 kcal"
        ),
        "colour": "#e74c3c",
        "calorie_factor": 22,
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
            "Breakfast: Eggs + Peanut Butter Oats\n"
            "Lunch: Chicken Biryani\n"
            "Dinner: Mutton Curry + Rice\n"
            "Target: ~3200 kcal"
        ),
        "colour": "#2ecc71",
        "calorie_factor": 35,
    },
    "BG": {
        "code": "BG",
        "name": "Beginner (BG)",
        "workout": (
            "Full Body Circuit:\n"
            "- Air Squats\n"
            "- Ring Rows\n"
            "- Push-ups\n"
            "Focus: Technique & Consistency"
        ),
        "diet": (
            "Balanced Tamil Meals\n"
            "Idli / Dosa / Rice + Dal\n"
            "Protein Target: 120g/day"
        ),
        "colour": "#3498db",
        "calorie_factor": 26,
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
