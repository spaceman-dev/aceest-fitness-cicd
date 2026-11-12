"""Business rules for ACEest Fitness & Gym.

Nothing in here imports Flask, so every rule can be unit tested on its own.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from datetime import date, datetime
from typing import Any

from .errors import ValidationError
from .programs import SITE_METRICS, WORKOUT_TYPES, get_program

NAME_PATTERN = re.compile(r"^[A-Za-z][A-Za-z .'\-]{1,49}$")
WEEK_PATTERN = re.compile(r"^(\d{4})-W(\d{2})$")
MIN_AGE, MAX_AGE = 10, 100
MIN_WEIGHT_KG, MAX_WEIGHT_KG = 25.0, 300.0
MIN_HEIGHT_CM, MAX_HEIGHT_CM = 90.0, 250.0
MAX_NOTES_LENGTH = 280
MAX_SESSION_MINUTES = 480


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


def validate_height_cm(value: Any) -> float:
    height = _as_number(value, "height_cm")
    if not MIN_HEIGHT_CM <= height <= MAX_HEIGHT_CM:
        raise ValidationError(
            f"'height_cm' must be between {MIN_HEIGHT_CM} and {MAX_HEIGHT_CM}", field="height_cm"
        )
    return round(height, 1)


def _optional(payload: Mapping[str, Any], field: str, validator) -> Any:
    value = payload.get(field)
    return None if value is None or value == "" else validator(value)


def _in_range(value: Any, field: str, low: float, high: float) -> float:
    number = _as_number(value, field)
    if not low <= number <= high:
        raise ValidationError(f"'{field}' must be between {low:g} and {high:g}", field=field)
    return round(number, 1)


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


def validate_iso_date(value: Any, field: str = "date") -> str:
    if value is None or value == "":
        return date.today().isoformat()
    try:
        return datetime.strptime(str(value).strip(), "%Y-%m-%d").date().isoformat()
    except ValueError:
        raise ValidationError(f"'{field}' must be a date like 2026-11-12", field=field) from None


def validate_workout(payload: Mapping[str, Any]) -> dict[str, Any]:
    """A logged session plus any exercises done in it."""
    workout_type = str(require(payload, "workout_type")).strip()
    match = [t for t in WORKOUT_TYPES if t.lower() == workout_type.lower()]
    if not match:
        raise ValidationError(
            f"'workout_type' must be one of {', '.join(WORKOUT_TYPES)}", field="workout_type"
        )
    duration = _as_int(require(payload, "duration_min"), "duration_min")
    if not 1 <= duration <= MAX_SESSION_MINUTES:
        raise ValidationError(
            f"'duration_min' must be between 1 and {MAX_SESSION_MINUTES}", field="duration_min"
        )
    exercises = payload.get("exercises") or []
    if not isinstance(exercises, list):
        raise ValidationError("'exercises' must be a list", field="exercises")
    return {
        "date": validate_iso_date(payload.get("date")),
        "workout_type": match[0],
        "duration_min": duration,
        "notes": validate_notes(payload.get("notes")),
        "exercises": [validate_exercise(item) for item in exercises],
    }


def validate_exercise(item: Any) -> dict[str, Any]:
    if not isinstance(item, Mapping):
        raise ValidationError("each exercise must be an object", field="exercises")
    name = str(require(item, "name")).strip()
    if not 1 <= len(name) <= 60:
        raise ValidationError("exercise 'name' must be 1-60 characters", field="name")
    sets = _as_int(require(item, "sets"), "sets")
    reps = _as_int(require(item, "reps"), "reps")
    if not 1 <= sets <= 20 or not 1 <= reps <= 100:
        raise ValidationError("'sets' must be 1-20 and 'reps' 1-100", field="sets")
    weight = item.get("weight_kg")
    return {
        "name": name,
        "sets": sets,
        "reps": reps,
        "weight_kg": 0.0 if weight in (None, "") else _in_range(weight, "weight_kg", 0, 500),
    }


def validate_metrics(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Body measurements for one day; at least one of the three is needed."""
    entry = {
        "date": validate_iso_date(payload.get("date")),
        "weight_kg": _optional(payload, "weight_kg", validate_weight_kg),
        "waist_cm": _optional(payload, "waist_cm", lambda v: _in_range(v, "waist_cm", 40, 250)),
        "bodyfat_pct": _optional(payload, "bodyfat_pct",
                                 lambda v: _in_range(v, "bodyfat_pct", 2, 70)),
    }
    if entry["weight_kg"] is None and entry["waist_cm"] is None and entry["bodyfat_pct"] is None:
        raise ValidationError("give at least one of weight_kg, waist_cm, bodyfat_pct",
                              field="weight_kg")
    return entry


def calculate_bmi(weight_kg: Any, height_cm: Any) -> float:
    height_m = validate_height_cm(height_cm) / 100.0
    return round(validate_weight_kg(weight_kg) / (height_m * height_m), 1)


def classify_bmi(bmi: float) -> dict[str, str]:
    """BMI band and the risk note the desktop build showed the coach."""
    if bmi < 18.5:
        return {"category": "Underweight", "risk": "Potential nutrient deficiency, low energy."}
    if bmi < 25:
        return {"category": "Normal", "risk": "Low risk if active and strong."}
    if bmi < 30:
        return {"category": "Overweight",
                "risk": "Moderate risk; focus on adherence and progressive activity."}
    return {"category": "Obese",
            "risk": "Higher risk; prioritize fat loss, consistency, and supervision."}


def bmi_report(weight_kg: Any, height_cm: Any) -> dict[str, Any]:
    bmi = calculate_bmi(weight_kg, height_cm)
    return {"bmi": bmi, **classify_bmi(bmi)}


def summarise_adherence(entries: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    values = [int(entry["adherence"]) for entry in entries]
    if not values:
        return {"weeks_logged": 0, "average_adherence": 0.0, "latest_adherence": None,
                "trend": "no data"}
    if len(values) > 1 and values[-1] > values[-2]:
        trend = "improving"
    elif len(values) > 1 and values[-1] < values[-2]:
        trend = "declining"
    else:
        trend = "steady"
    return {
        "weeks_logged": len(values),
        "average_adherence": round(sum(values) / len(values), 1),
        "latest_adherence": values[-1],
        "trend": trend,
    }


def capacity_used_pct(active_clients: int) -> float:
    return round(active_clients / SITE_METRICS["capacity_users"] * 100, 1)


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
        "height_cm": _optional(payload, "height_cm", validate_height_cm),
        "weight_kg": weight,
        "program": program["code"],
        "program_name": program["name"],
        "calories": int(weight * program["calorie_factor"]),
        "adherence": validate_adherence(adherence) if adherence not in (None, "") else 0,
        "notes": validate_notes(payload.get("notes")),
        "target_weight_kg": _optional(payload, "target_weight_kg", validate_weight_kg),
        "target_adherence": _optional(payload, "target_adherence", validate_adherence),
    }


def describe_client(client: Mapping[str, Any]) -> dict[str, Any]:
    """Stored client plus what is derived from it (program details, BMI)."""
    described = dict(client)
    program = get_program(client["program"]) or {}
    described["program_name"] = program.get("name", client["program"])
    described["program_notes"] = program.get("description", "")
    if client.get("height_cm"):
        described.update(bmi_report(client["weight_kg"], client["height_cm"]))
    return described
