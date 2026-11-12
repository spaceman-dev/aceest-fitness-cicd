"""Server-rendered dashboard and client pages."""

from __future__ import annotations

from typing import Any

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from .. import db
from ..errors import ACEestError, NotFoundError
from ..programs import SITE_METRICS, WORKOUT_TYPES, get_program, list_programs
from ..services import (
    build_profile,
    current_week,
    describe_client,
    summarise_adherence,
    validate_adherence,
    validate_metrics,
    validate_week,
    validate_workout,
)

web_bp = Blueprint("web", __name__)


def _dashboard(**context: Any) -> str:
    context.setdefault("selected", None)
    context.setdefault("form", {})
    return render_template(
        "dashboard.html",
        programs=list_programs(),
        metrics=SITE_METRICS,
        clients=[describe_client(client) for client in db.list_clients()],
        **context,
    )


def _client_or_404(name: str) -> dict[str, Any]:
    client = db.find_client(name)
    if client is None:
        raise NotFoundError(f"client '{name}' not found")
    return client


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
    """The desktop app's "Save Client": creates the client or updates it."""
    form = request.form.to_dict()
    try:
        profile = build_profile(form)
    except ACEestError as error:
        return _dashboard(form=form, error=error.message), error.status_code

    existing = db.find_client(profile["name"])
    if existing is None:
        db.insert_client(profile)
        message = f"Client {profile['name']} saved successfully. Adherence: {profile['adherence']}%"
    else:
        db.update_client(existing["id"], profile)
        message = f"Client {profile['name']} updated. Adherence: {profile['adherence']}%"
    return _dashboard(form=form, profile=profile, message=message,
                      selected=get_program(profile["program"]))


@web_bp.get("/clients/<name>")
def client_detail(name: str) -> Any:
    """The desktop app's "Load Client": profile summary plus weekly progress."""
    client = _client_or_404(name)
    progress = db.list_progress(client["id"])
    metrics = db.list_metrics(client["id"])
    return render_template(
        "client.html",
        client=describe_client(client),
        program=get_program(client["program"]),
        progress=progress,
        summary=summarise_adherence(progress),
        last_metrics=metrics[-1] if metrics else None,
        workouts=db.list_workouts(client["id"]),
        workout_types=WORKOUT_TYPES,
        week=current_week(),
    )


@web_bp.post("/clients/<name>/progress")
def save_progress(name: str) -> Any:
    client = _client_or_404(name)
    try:
        entry = db.save_progress(
            client["id"],
            validate_week(request.form.get("week")),
            validate_adherence(request.form.get("adherence")),
        )
        flash(f"Week {entry['week']} recorded at {entry['adherence']}%", "success")
    except ACEestError as error:
        flash(error.message, "error")
    return redirect(url_for("web.client_detail", name=client["name"]), code=303)


@web_bp.post("/clients/<name>/workouts")
def save_workout(name: str) -> Any:
    client = _client_or_404(name)
    form = request.form.to_dict()
    exercise = {key: form.pop(f"exercise_{key}", "")
                for key in ("name", "sets", "reps", "weight_kg")}
    if exercise["name"]:
        form["exercises"] = [exercise]
    try:
        workout = db.insert_workout(client["id"], validate_workout(form))
        flash(f"{workout['workout_type']} session on {workout['date']} logged", "success")
    except ACEestError as error:
        flash(error.message, "error")
    return redirect(url_for("web.client_detail", name=client["name"]), code=303)


@web_bp.post("/clients/<name>/metrics")
def save_metrics(name: str) -> Any:
    client = _client_or_404(name)
    try:
        entry = db.insert_metrics(client["id"], validate_metrics(request.form.to_dict()))
        flash(f"Body metrics for {entry['date']} logged", "success")
    except ACEestError as error:
        flash(error.message, "error")
    return redirect(url_for("web.client_detail", name=client["name"]), code=303)
