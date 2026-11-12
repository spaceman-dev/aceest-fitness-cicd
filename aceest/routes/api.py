"""JSON API."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from flask import Blueprint, Response, current_app, jsonify, request

from .. import db
from ..errors import ConflictError, NotFoundError, ValidationError
from ..exports import clients_to_csv
from ..programs import SITE_METRICS, get_program, list_programs
from ..services import (
    build_profile,
    calculate_calories,
    require,
    validate_adherence,
    validate_program,
    validate_week,
    validate_weight_kg,
)

api_bp = Blueprint("api", __name__, url_prefix="/api")


def _json_body() -> Mapping[str, Any]:
    body = request.get_json(silent=True)
    if not isinstance(body, Mapping):
        raise ValidationError("request body must be a JSON object")
    return body


@api_bp.get("/health")
def health() -> Any:
    from .. import __version__

    return jsonify({
        "status": "healthy",
        "service": "aceest-fitness",
        "version": __version__,
        "track": current_app.config["TRACK"],
    })


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


@api_bp.get("/site")
def site() -> Any:
    return jsonify(SITE_METRICS)


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


@api_bp.post("/profile")
def profile() -> Any:
    """Validate a client profile and return it with its calorie estimate."""
    return jsonify(build_profile(_json_body()))


def _client_or_404(name: str) -> dict[str, Any]:
    client = db.find_client(name)
    if client is None:
        raise NotFoundError(f"client '{name}' not found")
    return client


@api_bp.get("/clients")
def list_clients() -> Any:
    clients = db.list_clients()
    return jsonify({"clients": clients, "count": len(clients)})


@api_bp.post("/clients")
def add_client() -> Any:
    profile = build_profile(_json_body())
    if db.find_client(profile["name"]) is not None:
        raise ConflictError(f"client '{profile['name']}' already exists", field="name")
    return jsonify(db.insert_client(profile)), 201


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
    client["progress"] = db.list_progress(client["id"])
    return jsonify(client)


@api_bp.put("/clients/<name>")
def update_client(name: str) -> Any:
    client = _client_or_404(name)
    body = dict(_json_body())
    body.setdefault("name", client["name"])
    profile = build_profile(body)
    clash = db.find_client(profile["name"])
    if clash is not None and clash["id"] != client["id"]:
        raise ConflictError(f"client '{profile['name']}' already exists", field="name")
    return jsonify(db.update_client(client["id"], profile))


@api_bp.get("/clients/<name>/progress")
def get_progress(name: str) -> Any:
    client = _client_or_404(name)
    return jsonify({"client": client["name"], "entries": db.list_progress(client["id"])})


@api_bp.post("/clients/<name>/progress")
def log_progress(name: str) -> Any:
    client = _client_or_404(name)
    body = _json_body()
    entry = db.insert_progress(
        client["id"],
        validate_week(body.get("week")),
        validate_adherence(require(body, "adherence")),
    )
    return jsonify(entry), 201
