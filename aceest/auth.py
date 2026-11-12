"""Staff logins and roles (3.1.2 added a login screen to the desktop app).

The desktop build shipped a default admin/admin account. Here nothing is
hard-coded: the first Admin is created from ACEEST_ADMIN_PASSWORD (a
Kubernetes Secret in the cluster) the first time the app starts against an
empty users table. Passwords are stored as scrypt hashes.

Browsers sign in with a session cookie; API clients may also send HTTP Basic
credentials.
"""

from __future__ import annotations

import logging
import re
import sqlite3
from collections.abc import Callable
from functools import wraps
from typing import Any
from urllib.parse import urlsplit

from flask import Flask, abort, g, request, session
from werkzeug.security import check_password_hash, generate_password_hash

from . import db
from .errors import ConflictError, ValidationError

log = logging.getLogger(__name__)

ROLES = ("Admin", "Coach")
USERNAME_PATTERN = re.compile(r"^[a-z][a-z0-9_.-]{2,31}$")
MIN_PASSWORD_LENGTH = 10


def validate_username(value: Any) -> str:
    username = str(value or "").strip().lower()
    if not USERNAME_PATTERN.match(username):
        raise ValidationError(
            "'username' must be 3-32 characters: lowercase letters, digits, . _ -",
            field="username",
        )
    return username


def validate_password(value: Any) -> str:
    if not isinstance(value, str) or len(value) < MIN_PASSWORD_LENGTH:
        raise ValidationError(
            f"'password' must be at least {MIN_PASSWORD_LENGTH} characters", field="password"
        )
    return value


def validate_role(value: Any) -> str:
    for role in ROLES:
        if str(value or "").strip().lower() == role.lower():
            return role
    raise ValidationError(f"'role' must be one of {', '.join(ROLES)}", field="role")


def create_user(username: Any, password: Any, role: Any) -> dict[str, Any]:
    name = validate_username(username)
    secret = validate_password(password)
    level = validate_role(role)
    if db.find_user(name) is not None:
        raise ConflictError(f"user '{name}' already exists", field="username")
    return db.insert_user(name, generate_password_hash(secret), level)


def authenticate(username: Any, password: Any) -> dict[str, Any] | None:
    user = db.find_user(str(username or "").strip().lower())
    if user is None or not check_password_hash(user["password_hash"], str(password or "")):
        return None
    return user


def seed_admin(app: Flask) -> None:
    """Create the first Admin from ACEEST_ADMIN_PASSWORD if there are no users yet."""
    password = app.config.get("ADMIN_PASSWORD")
    with app.app_context():
        if db.count_users():
            return
        if not password:
            log.warning("no users and no ACEEST_ADMIN_PASSWORD set - nobody can sign in yet")
            return
        try:
            create_user("admin", password, "Admin")
            log.info("created the initial admin account")
        except (ConflictError, sqlite3.IntegrityError):
            pass  # another replica created it first


def load_user() -> None:
    """Resolve the caller from the session cookie or HTTP Basic credentials."""
    g.user = None
    user_id = session.get("user_id")
    if user_id is not None:
        g.user = db.find_user_by_id(user_id)
    elif request.authorization and request.authorization.type == "basic":
        g.user = authenticate(request.authorization.username, request.authorization.password)


def admin_required(view: Callable) -> Callable:
    @wraps(view)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        if g.get("user") is None or g.user["role"] != "Admin":
            abort(403, description="Admins only")
        return view(*args, **kwargs)
    return wrapper


def safe_next(target: str | None) -> str | None:
    """Only follow ?next= back into this site, never to another host."""
    if not target:
        return None
    parts = urlsplit(target)
    if parts.scheme or parts.netloc or not target.startswith("/") or target.startswith("//"):
        return None
    return target
