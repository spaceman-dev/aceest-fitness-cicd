"""ACEest Fitness & Gym - Flask application factory."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from flask import Flask, g, jsonify, request
from flask_wtf.csrf import CSRFProtect
from werkzeug.exceptions import HTTPException

from . import auth, db, observability
from .config import get_config
from .errors import ACEestError

__version__ = "3.0.1"

csrf = CSRFProtect()


def create_app(config_name: str | None = None,
               overrides: Mapping[str, Any] | None = None) -> Flask:
    """Build a configured Flask application."""
    app = Flask(__name__)
    app.config.from_object(get_config(config_name))
    if overrides:
        app.config.update(overrides)
    app.json.sort_keys = False

    db.init_app(app)
    auth.seed_admin(app)
    csrf.init_app(app)
    observability.init_app(app)
    app.before_request(auth.load_user)
    _register_blueprints(app)
    _register_error_handlers(app)
    _register_release_info(app)
    return app


def _register_blueprints(app: Flask) -> None:
    from .routes.api import api_bp
    from .routes.auth import auth_bp
    from .routes.web import web_bp

    # The JSON API takes no cookies and only JSON bodies, which a cross-site
    # form cannot send, so CSRF tokens apply to the HTML forms only.
    csrf.exempt(api_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(web_bp)


def _register_release_info(app: Flask) -> None:
    """Stamp every response with the build that served it.

    During blue-green, canary or A/B rollouts two versions answer on the same
    URL, so the headers are how a test (or a person) tells them apart.
    """

    @app.after_request
    def add_release_headers(response):
        response.headers["X-ACEest-Version"] = __version__
        response.headers["X-ACEest-Track"] = app.config["TRACK"]
        return response

    @app.context_processor
    def inject_release() -> dict[str, Any]:
        return {"app_version": __version__, "app_track": app.config["TRACK"],
                "current_user": g.get("user")}


def _wants_json() -> bool:
    return request.path.startswith("/api")


def _register_error_handlers(app: Flask) -> None:
    @app.errorhandler(ACEestError)
    def handle_domain_error(error: ACEestError):
        return jsonify(error.to_dict()), error.status_code

    @app.errorhandler(HTTPException)
    def handle_http_error(error: HTTPException):
        if _wants_json():
            return jsonify({"error": error.name, "message": error.description}), error.code
        return error
