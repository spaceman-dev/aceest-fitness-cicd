"""JSON API."""

from __future__ import annotations

from typing import Any

from flask import Blueprint, current_app, jsonify

from ..errors import NotFoundError
from ..programs import SITE_METRICS, get_program, list_programs

api_bp = Blueprint("api", __name__, url_prefix="/api")


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
