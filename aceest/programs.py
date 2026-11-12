"""Training program catalogue (as of Aceestver-2.2.4).

``calorie_factor`` is kcal per kg of body weight per day. 2.2.4 split Fat
Loss into a 3-day and a 5-day program; the old ``FL`` code still resolves
to ``FL3`` so existing clients and API callers keep working.
"""

from __future__ import annotations

from typing import Any

PROGRAMS: dict[str, dict[str, Any]] = {
    "FL3": {
        "code": "FL3",
        "name": "Fat Loss (FL) - 3 day",
        "description": "3-day full-body fat loss",
        "calorie_factor": 22,
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
    },
    "FL5": {
        "code": "FL5",
        "name": "Fat Loss (FL) - 5 day",
        "description": "5-day split, higher volume fat loss",
        "calorie_factor": 24,
        "workout": (
            "Mon: Lower Strength + Intervals\n"
            "Tue: Upper Push + Conditioning\n"
            "Wed: Steady State 40min\n"
            "Thu: Upper Pull + Core\n"
            "Fri: Full Body Metcon"
        ),
        "diet": (
            "Breakfast: Oats Idli + Egg Whites\n"
            "Lunch: Grilled Fish + Quinoa\n"
            "Dinner: Chicken Curry + Millet Roti\n"
            "Target: ~2200 kcal"
        ),
        "colour": "#e67e22",
    },
    "MG": {
        "code": "MG",
        "name": "Muscle Gain (MG) - PPL",
        "description": "Push/Pull/Legs hypertrophy",
        "calorie_factor": 35,
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
    },
    "BG": {
        "code": "BG",
        "name": "Beginner (BG)",
        "description": "3-day simple beginner full-body",
        "calorie_factor": 26,
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
    },
}

ALIASES = {"FL": "FL3"}

# Training templates per program (Aceestver-3.2.4's program_templates).
TEMPLATES: dict[str, tuple[str, ...]] = {
    "FL3": ("Full Body HIIT", "Circuit Training", "Cardio + Weights"),
    "FL5": ("Full Body HIIT", "Circuit Training", "Cardio + Weights"),
    "MG": ("Push/Pull/Legs", "Upper/Lower Split", "Full Body Strength"),
    "BG": ("Full Body 3x/week", "Light Strength + Mobility"),
}

WORKOUT_TYPES = ("Strength", "Hypertrophy", "Conditioning", "Mixed", "Mobility")

# Reference figures for the site, shown on the dashboard.
SITE_METRICS = {
    "capacity_users": 150,
    "area_sq_ft": 10000,
    "break_even_members": 250,
}


def list_programs() -> list[dict[str, Any]]:
    return list(PROGRAMS.values())


def templates_for(code: str) -> tuple[str, ...]:
    program = get_program(code)
    return TEMPLATES[program["code"]] if program else ()


def get_program(code: Any) -> dict[str, Any] | None:
    """Look a program up by code, ignoring case and surrounding spaces."""
    if not isinstance(code, str):
        return None
    key = code.strip().upper()
    return PROGRAMS.get(ALIASES.get(key, key))
