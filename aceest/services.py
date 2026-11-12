"""Business rules for ACEest Fitness & Gym.

Nothing in here imports Flask, so every rule can be unit tested on its own.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import date
from typing import Any

from .errors import ValidationError
from .programs import get_program

NAME_PATTERN = re.compile(r"^[A-Za-z][A-Za-z .'\-]{1,49}$")
WEEK_PATTERN = re.compile(r"^(\d{4})-W(\d{2})$")
MIN_AGE, MAX_AGE = 10, 100
MIN_WEIGHT_KG, MAX_WEIGHT_KG = 25.0, 300.0
MAX_NOTES_LENGTH = 280


def require(payload: Mapping[str, Any], field: str) -> Any:
    value = payload.get(field)
    if value is None or value == "":
        raise ValidationError(f"'{field}' is required", field=field)
    return value


def _as_number(value: Any, field: str) -> float:
    if isinstance(value, bool):
        raise ValidationError(f"'{field}' must be a number", field=field)
    try:
        return float(value)
    except (TypeError, ValueError):
        raise ValidationError(f"'{field}' must be a number", field=field) from None


def _as_int(value: Any, field: str) -> int:
    number = _as_number(value, field)
    if number != int(number):
        raise ValidationError(f"'{field}' must be a whole number", field=field)
    return int(number)


def validate_name(value: Any) -> str:
    if not isinstance(value, str):
        raise ValidationError("'name' must be text", field="name")
    name = " ".join(value.split())
    if not NAME_PATTERN.match(name):
        raise ValidationError("'name' must be 2-50 letters and start with a letter", field="name")
    return name


def validate_age(value: Any) -> int:
    age = _as_int(value, "age")
    if not MIN_AGE <= age <= MAX_AGE:
        raise ValidationError(f"'age' must be between {MIN_AGE} and {MAX_AGE}", field="age")
    return age


def validate_weight_kg(value: Any) -> float:
    weight = _as_number(value, "weight_kg")
    if not MIN_WEIGHT_KG <= weight <= MAX_WEIGHT_KG:
        raise ValidationError(
            f"'weight_kg' must be between {MIN_WEIGHT_KG} and {MAX_WEIGHT_KG}", field="weight_kg"
        )
    return round(weight, 1)


def validate_program(value: Any) -> dict[str, Any]:
    program = get_program(value)
    if program is None:
        raise ValidationError(f"unknown program '{value}'", field="program")
    return program


def validate_adherence(value: Any) -> int:
    adherence = _as_int(value, "adherence")
    if not 0 <= adherence <= 100:
        raise ValidationError("'adherence' must be between 0 and 100", field="adherence")
    return adherence


def validate_notes(value: Any) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ValidationError("'notes' must be text", field="notes")
    notes = value.strip()
    if len(notes) > MAX_NOTES_LENGTH:
        raise ValidationError(
            f"'notes' must be {MAX_NOTES_LENGTH} characters or fewer", field="notes"
        )
    return notes


def current_week(today: date | None = None) -> str:
    """ISO week label, e.g. 2026-W46 (the desktop build used 'Week %U - %Y')."""
    year, week, _ = (today or date.today()).isocalendar()
    return f"{year}-W{week:02d}"


def validate_week(value: Any) -> str:
    if value is None or value == "":
        return current_week()
    match = WEEK_PATTERN.match(value.strip()) if isinstance(value, str) else None
    if not match or not 1 <= int(match.group(2)) <= 53:
        raise ValidationError("'week' must look like 2026-W46", field="week")
    return value.strip()


def calculate_calories(weight_kg: Any, program: Any) -> int:
    """Daily calorie estimate: body weight (kg) x the program's calorie factor."""
    weight = validate_weight_kg(weight_kg)
    return int(weight * validate_program(program)["calorie_factor"])


def build_profile(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Validate a client profile and derive its calorie estimate."""
    if not isinstance(payload, Mapping):
        raise ValidationError("request body must be a JSON object")
    program = validate_program(require(payload, "program"))
    weight = validate_weight_kg(require(payload, "weight_kg"))
    adherence = payload.get("adherence")
    return {
        "name": validate_name(require(payload, "name")),
        "age": validate_age(require(payload, "age")),
        "weight_kg": weight,
        "program": program["code"],
        "program_name": program["name"],
        "calories": int(weight * program["calorie_factor"]),
        "adherence": validate_adherence(adherence) if adherence not in (None, "") else 0,
        "notes": validate_notes(payload.get("notes")),
    }
