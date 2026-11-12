"""JSON API."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from flask import Blueprint, Response, current_app, jsonify, request

from ..errors import NotFoundError, ValidationError
from ..exports import clients_to_csv
from ..programs import SITE_METRICS, get_program, list_programs
from ..services import (
    build_profile,
    calculate_calories,
    require,
    validate_program,
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


def _roster():
    return current_app.extensions["aceest_roster"]


@api_bp.get("/clients")
def list_clients() -> Any:
    clients = _roster().all()
    return jsonify({"clients": clients, "count": len(clients)})


@api_bp.post("/clients")
def add_client() -> Any:
    client = _roster().add(build_profile(_json_body()))
    return jsonify(client), 201


@api_bp.get("/clients/export.csv")
def export_clients() -> Any:
    return Response(
        clients_to_csv(_roster().all()),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=aceest_clients.csv"},
    )
