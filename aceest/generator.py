"""Weekly program generator - the "Generate AI Program" button of Aceestver-3.1.2.

The desktop build drew exercises with random.sample, so every click gave a
different plan. Here the pick is ranked by a hash of client, ISO week, day
and exercise: the same client sees the same plan all week (a refresh does not
reshuffle it) and gets a fresh one the next week.
"""

from __future__ import annotations

import hashlib
from typing import Any

from .errors import ValidationError

EXERCISE_POOLS: dict[str, tuple[str, ...]] = {
    "Strength": ("Squat", "Deadlift", "Bench Press", "Overhead Press", "Pull-Up", "Barbell Row"),
    "Hypertrophy": ("Leg Press", "Incline Dumbbell Press", "Lat Pulldown", "Lateral Raise",
                    "Bicep Curl", "Tricep Extension"),
    "Conditioning": ("Running", "Cycling", "Rowing", "Burpees", "Jump Rope", "Kettlebell Swings"),
    "Full Body": ("Push-Up", "Pull-Up", "Lunge", "Plank", "Dumbbell Row", "Dumbbell Press"),
}

LEVELS: dict[str, dict[str, Any]] = {
    "beginner": {"days": 3, "sets": (2, 3), "reps": (8, 12)},
    "intermediate": {"days": 4, "sets": (3, 4), "reps": (8, 15)},
    "advanced": {"days": 5, "sets": (4, 5), "reps": (6, 15)},
}

WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday")


def focus_for(program_code: str) -> str:
    if program_code in ("FL3", "FL5"):
        return "Conditioning"
    if program_code == "MG":
        return "Hypertrophy"
    return "Full Body"


def _rank(*parts: str) -> int:
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big")


def _pick(low: int, high: int, *parts: str) -> int:
    return low + _rank(*parts) % (high - low + 1)


def generate_program(client: str, program_code: str, level: Any, week: str) -> dict[str, Any]:
    key = str(level or "").strip().lower()
    if key not in LEVELS:
        raise ValidationError("'experience' must be beginner, intermediate or advanced",
                              field="experience")
    rules = LEVELS[key]
    focus = focus_for(program_code)
    per_day = 3 if rules["days"] < 4 else 4
    sessions = []
    for day in WEEKDAYS[:rules["days"]]:
        ranked = sorted(EXERCISE_POOLS[focus], key=lambda name, d=day: _rank(client, week, d, name))
        for exercise in ranked[:per_day]:
            sessions.append({
                "day": day,
                "exercise": exercise,
                "sets": _pick(*rules["sets"], client, week, day, exercise, "sets"),
                "reps": _pick(*rules["reps"], client, week, day, exercise, "reps"),
            })
    return {"client": client, "focus": focus, "experience": key, "week": week,
            "days": rules["days"], "sessions": sessions}
