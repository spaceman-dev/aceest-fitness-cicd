"""Server-rendered dashboard."""

from __future__ import annotations

from typing import Any

from flask import Blueprint, abort, current_app, render_template, request

from ..errors import ValidationError
from ..programs import SITE_METRICS, get_program, list_programs
from ..services import build_profile

web_bp = Blueprint("web", __name__)


def _dashboard(**context: Any) -> str:
    context.setdefault("selected", None)
    context.setdefault("form", {})
    return render_template(
        "dashboard.html",
        programs=list_programs(),
        metrics=SITE_METRICS,
        clients=current_app.extensions["aceest_roster"].all(),
        **context,
    )


@web_bp.get("/")
def dashboard() -> Any:
    selected = None
    code = request.args.get("program")
    if code:
        selected = get_program(code)
        if selected is None:
            abort(404, description=f"program '{code}' not found")
    return _dashboard(selected=selected)


@web_bp.post("/profile")
def save_profile() -> Any:
    form = request.form.to_dict()
    try:
        profile = current_app.extensions["aceest_roster"].add(build_profile(form))
    except ValidationError as error:
        return _dashboard(form=form, error=error.message), 400
    return _dashboard(form=form, profile=profile, selected=get_program(profile["program"]))
