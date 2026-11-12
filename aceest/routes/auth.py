"""Sign in / sign out and user management (Admins only)."""

from __future__ import annotations

from typing import Any

from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from .. import db
from ..auth import admin_required, authenticate, create_user, safe_next
from ..errors import ACEestError

auth_bp = Blueprint("auth", __name__)


@auth_bp.get("/login")
def login() -> Any:
    return render_template("login.html", next=request.args.get("next", ""))


@auth_bp.post("/login")
def login_submit() -> Any:
    user = authenticate(request.form.get("username"), request.form.get("password"))
    if user is None:
        return render_template("login.html", error="Invalid username or password",
                               next=request.form.get("next", "")), 401
    session.clear()  # a fresh session on every sign-in
    session["user_id"] = user["id"]
    return redirect(safe_next(request.form.get("next")) or url_for("web.dashboard"), code=303)


@auth_bp.post("/logout")
def logout() -> Any:
    session.clear()
    return redirect(url_for("auth.login"), code=303)


@auth_bp.get("/users")
@admin_required
def users() -> Any:
    return render_template("users.html", users=db.list_users())


@auth_bp.post("/users")
@admin_required
def add_user() -> Any:
    try:
        user = create_user(request.form.get("username"), request.form.get("password"),
                           request.form.get("role"))
        flash(f"User {user['username']} ({user['role']}) created", "success")
    except ACEestError as error:
        flash(error.message, "error")
    return redirect(url_for("auth.users"), code=303)
