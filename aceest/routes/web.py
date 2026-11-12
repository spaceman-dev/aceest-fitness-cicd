"""Server-rendered dashboard."""

from __future__ import annotations

from typing import Any

from flask import Blueprint, abort, render_template, request

from ..programs import SITE_METRICS, get_program, list_programs

web_bp = Blueprint("web", __name__)


@web_bp.get("/")
def dashboard() -> Any:
    selected = None
    code = request.args.get("program")
    if code:
        selected = get_program(code)
        if selected is None:
            abort(404, description=f"program '{code}' not found")
    return render_template(
        "dashboard.html",
        programs=list_programs(),
        selected=selected,
        metrics=SITE_METRICS,
    )
