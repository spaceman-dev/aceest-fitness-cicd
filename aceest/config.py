"""Environment driven configuration."""

from __future__ import annotations

import os


class BaseConfig:
    # Never a hard-coded key: without SECRET_KEY each process gets a random one.
    SECRET_KEY = os.environ.get("SECRET_KEY") or os.urandom(32).hex()
    # Which deployment slot/track this process belongs to (blue, canary, ...).
    TRACK = os.environ.get("ACEEST_TRACK", "local")
    # SQLite file; the container points this at the /data volume
    DATABASE = os.environ.get("ACEEST_DB", "aceest_fitness.db")
    # rollback drills only: "unhealthy" or "errors" (see aceest/observability.py)
    FAULT = os.environ.get("ACEEST_FAULT", "").strip().lower()
    TESTING = False
    DEBUG = False


class DevelopmentConfig(BaseConfig):
    DEBUG = True


class TestingConfig(BaseConfig):
    TESTING = True


class ProductionConfig(BaseConfig):
    pass


CONFIGS = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}


def get_config(name: str | None = None) -> type[BaseConfig]:
    key = (name or os.environ.get("FLASK_ENV") or "production").strip().lower()
    return CONFIGS.get(key, ProductionConfig)
