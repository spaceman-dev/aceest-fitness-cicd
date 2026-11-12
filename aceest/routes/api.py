"""JSON API."""

from __future__ import annotations

import sqlite3
from collections import Counter
from collections.abc import Mapping
from typing import Any

from datetime import date

from flask import Blueprint, Response, current_app, g, jsonify, request

from .. import db
from ..auth import admin_required, create_user
from ..charts import line_chart
from ..errors import ConflictError, NotFoundError, ValidationError
from ..exports import clients_to_csv
from ..generator import generate_program
from ..programs import SITE_METRICS, WORKOUT_TYPES, get_program, list_programs
from ..reports import client_report
from ..services import (
    bmi_report,
    build_profile,
    calculate_calories,
    capacity_used_pct,
    current_week,
    describe_client,
    require,
    summarise_adherence,
    validate_adherence,
    validate_metrics,
    validate_program,
    validate_week,
    validate_weight_kg,
    validate_workout,
)

api_bp = Blueprint("api", __name__, url_prefix="/api")

PROTECTED_PREFIXES = ("/api/clients", "/api/users")


@api_bp.before_request
def require_credentials() -> Any:
    """Client records are personal data: only signed-in staff may read or change them."""
    if request.path.startswith(PROTECTED_PREFIXES) and g.get("user") is None:
        response = jsonify({"error": "Unauthorized",
                            "message": "sign in or send Basic credentials"})
        response.headers["WWW-Authenticate"] = 'Basic realm="ACEest"'
        return response, 401
    return None


def _json_body() -> Mapping[str, Any]:
    body = request.get_json(silent=True)
    if not isinstance(body, Mapping):
        raise ValidationError("request body must be a JSON object")
    return body


@api_bp.get("/health")
def health() -> Any:
    from .. import __version__

    try:
        db.get_db().execute("SELECT 1").fetchone()
        database = "ok"
    except sqlite3.Error:
        database = "unavailable"
    healthy = database == "ok"
    return jsonify({
        "status": "healthy" if healthy else "unhealthy",
        "service": "aceest-fitness",
        "version": __version__,
        "track": current_app.config["TRACK"],
        "checks": {"database": database},
    }), (200 if healthy else 503)


@api_bp.get("/programs")
def programs() -> Any:
    catalogue = list_programs()
    return jsonify({"programs": catalogue, "count": len(catalogue)})


@api_bp.get("/programs/<code>")
def program_detail(code: str) -> Any:
    program = get_program(code)
    if program is None:
        raise NotFoundError(f"program '{code}' not found")
    return jsonify(program)


@api_bp.get("/stats")
def stats() -> Any:
    clients = db.list_clients()
    total = len(clients)
    return jsonify({
        "total_clients": total,
        "clients_by_program": dict(Counter(client["program"] for client in clients)),
        "average_calorie_target": (
            round(sum(client["calories"] for client in clients) / total, 1) if total else 0.0
        ),
        "capacity_used_pct": capacity_used_pct(total),
        "site_metrics": SITE_METRICS,
        "workout_types": list(WORKOUT_TYPES),
    })


@api_bp.post("/calories")
def calories() -> Any:
    body = _json_body()
    weight = validate_weight_kg(require(body, "weight_kg"))
    program = validate_program(require(body, "program"))
    return jsonify({
        "weight_kg": weight,
        "program": program["code"],
        "program_name": program["name"],
        "factor": program["calorie_factor"],
        "calories": calculate_calories(weight, program["code"]),
    })


@api_bp.post("/bmi")
def bmi() -> Any:
    body = _json_body()
    return jsonify(bmi_report(require(body, "weight_kg"), require(body, "height_cm")))


def _client_or_404(name: str) -> dict[str, Any]:
    client = db.find_client(name)
    if client is None:
        raise NotFoundError(f"client '{name}' not found")
    return client


@api_bp.get("/clients")
def list_clients() -> Any:
    clients = [describe_client(client) for client in db.list_clients()]
    return jsonify({"clients": clients, "count": len(clients)})


@api_bp.post("/clients")
def add_client() -> Any:
    profile = build_profile(_json_body())
    if db.find_client(profile["name"]) is not None:
        raise ConflictError(f"client '{profile['name']}' already exists", field="name")
    return jsonify(describe_client(db.insert_client(profile))), 201


@api_bp.get("/clients/export.csv")
def export_clients() -> Any:
    return Response(
        clients_to_csv(db.list_clients()),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=aceest_clients.csv"},
    )


@api_bp.get("/clients/<name>")
def get_client(name: str) -> Any:
    client = _client_or_404(name)
    payload = describe_client(client)
    payload["progress"] = db.list_progress(client["id"])
    payload["progress_summary"] = summarise_adherence(payload["progress"])
    metrics = db.list_metrics(client["id"])
    payload["last_metrics"] = metrics[-1] if metrics else None
    payload["workouts"] = db.list_workouts(client["id"])
    return jsonify(payload)


@api_bp.put("/clients/<name>")
def update_client(name: str) -> Any:
    client = _client_or_404(name)
    body = dict(_json_body())
    body.setdefault("name", client["name"])
    profile = build_profile(body)
    clash = db.find_client(profile["name"])
    if clash is not None and clash["id"] != client["id"]:
        raise ConflictError(f"client '{profile['name']}' already exists", field="name")
    return jsonify(describe_client(db.update_client(client["id"], profile)))


@api_bp.get("/clients/<name>/progress")
def get_progress(name: str) -> Any:
    client = _client_or_404(name)
    return jsonify({"client": client["name"], "entries": db.list_progress(client["id"])})


@api_bp.post("/clients/<name>/progress")
def log_progress(name: str) -> Any:
    client = _client_or_404(name)
    body = _json_body()
    entry = db.save_progress(
        client["id"],
        validate_week(body.get("week")),
        validate_adherence(require(body, "adherence")),
    )
    return jsonify(entry), 201


@api_bp.get("/clients/<name>/progress/chart.svg")
def progress_chart(name: str) -> Any:
    client = _client_or_404(name)
    points = [(entry["week"], entry["adherence"]) for entry in db.list_progress(client["id"])]
    svg = line_chart(f"Weekly adherence - {client['name']}", points)
    return Response(svg, mimetype="image/svg+xml")


@api_bp.get("/clients/<name>/workouts")
def get_workouts(name: str) -> Any:
    client = _client_or_404(name)
    workouts = db.list_workouts(client["id"])
    return jsonify({
        "client": client["name"],
        "workouts": workouts,
        "count": len(workouts),
        "total_minutes": sum(w["duration_min"] for w in workouts),
    })


@api_bp.post("/clients/<name>/workouts")
def log_workout(name: str) -> Any:
    client = _client_or_404(name)
    return jsonify(db.insert_workout(client["id"], validate_workout(_json_body()))), 201


@api_bp.get("/clients/<name>/metrics")
def get_metrics(name: str) -> Any:
    client = _client_or_404(name)
    return jsonify({"client": client["name"], "entries": db.list_metrics(client["id"])})


@api_bp.post("/clients/<name>/metrics")
def log_metrics(name: str) -> Any:
    client = _client_or_404(name)
    return jsonify(db.insert_metrics(client["id"], validate_metrics(_json_body()))), 201


@api_bp.get("/clients/<name>/metrics/chart.svg")
def weight_chart(name: str) -> Any:
    client = _client_or_404(name)
    points = [(m["date"], m["weight_kg"]) for m in db.list_metrics(client["id"])
              if m["weight_kg"] is not None]
    weights = [value for _, value in points] or [client["weight_kg"]]
    svg = line_chart(f"Weight trend - {client['name']}", points, unit=" kg", colour="#e67e22",
                     y_min=max(min(weights) - 5, 0), y_max=max(weights) + 5)
    return Response(svg, mimetype="image/svg+xml")


@api_bp.get("/clients/<name>/program")
def client_program(name: str) -> Any:
    client = _client_or_404(name)
    return jsonify(generate_program(client["name"], client["program"],
                                    request.args.get("experience"), current_week()))


@api_bp.get("/clients/<name>/report.pdf")
def client_pdf(name: str) -> Any:
    client = _client_or_404(name)
    pdf = client_report(describe_client(client),
                        summarise_adherence(db.list_progress(client["id"])),
                        db.list_workouts(client["id"]), date.today().isoformat())
    return Response(pdf, mimetype="application/pdf")


@api_bp.get("/users")
@admin_required
def list_users() -> Any:
    return jsonify({"users": db.list_users()})


@api_bp.post("/users")
@admin_required
def add_user() -> Any:
    body = _json_body()
    return jsonify(create_user(body.get("username"), body.get("password"), body.get("role"))), 201
