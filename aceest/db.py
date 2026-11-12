"""SQLite persistence (introduced in 2.0.1, as in Aceestver2.0.1).

One connection per request and parameterised SQL only. Schema changes are
numbered migrations recorded in ``schema_version`` and applied at start-up.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Mapping
from typing import Any

from flask import Flask, current_app, g

MIGRATIONS: list[tuple[int, list[str]]] = [
    (1, [
        """
        CREATE TABLE IF NOT EXISTS clients (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            name       TEXT    NOT NULL UNIQUE COLLATE NOCASE,
            age        INTEGER NOT NULL,
            weight_kg  REAL    NOT NULL,
            program    TEXT    NOT NULL,
            calories   INTEGER NOT NULL,
            adherence  INTEGER NOT NULL DEFAULT 0,
            notes      TEXT    NOT NULL DEFAULT '',
            created_at TEXT    NOT NULL DEFAULT (datetime('now'))
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS progress (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
            week      TEXT    NOT NULL,
            adherence INTEGER NOT NULL,
            logged_at TEXT    NOT NULL DEFAULT (datetime('now'))
        )
        """,
    ]),
]


def connect(path: str) -> sqlite3.Connection:
    connection = sqlite3.connect(path, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def migrate(connection: sqlite3.Connection) -> int:
    """Bring the schema up to date; returns the resulting version."""
    # IMMEDIATE takes the write lock up front, so replicas starting together
    # against the same file run the migrations one after the other.
    connection.execute("BEGIN IMMEDIATE")
    try:
        connection.execute(
            "CREATE TABLE IF NOT EXISTS schema_version (version INTEGER PRIMARY KEY)"
        )
        current = connection.execute(
            "SELECT COALESCE(MAX(version), 0) FROM schema_version"
        ).fetchone()[0]
        for version, statements in MIGRATIONS:
            if version > current:
                for statement in statements:
                    connection.execute(statement)
                connection.execute("INSERT INTO schema_version (version) VALUES (?)", (version,))
                current = version
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    return current


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        g.db = connect(current_app.config["DATABASE"])
    return g.db


def close_db(_error: BaseException | None = None) -> None:
    connection = g.pop("db", None)
    if connection is not None:
        connection.close()


def init_app(app: Flask) -> None:
    app.teardown_appcontext(close_db)
    connection = connect(app.config["DATABASE"])
    try:
        migrate(connection)
    finally:
        connection.close()


def _one(sql: str, params: tuple[Any, ...]) -> dict[str, Any] | None:
    row = get_db().execute(sql, params).fetchone()
    return dict(row) if row is not None else None


def _all(sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    return [dict(row) for row in get_db().execute(sql, params).fetchall()]


# ------------------------------------------------------------------ clients


def list_clients() -> list[dict[str, Any]]:
    return _all("SELECT * FROM clients ORDER BY name")


def find_client(name: str) -> dict[str, Any] | None:
    return _one("SELECT * FROM clients WHERE name = ?", (name,))


def insert_client(profile: Mapping[str, Any]) -> dict[str, Any]:
    db = get_db()
    cursor = db.execute(
        """
        INSERT INTO clients (name, age, weight_kg, program, calories, adherence, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (profile["name"], profile["age"], profile["weight_kg"], profile["program"],
         profile["calories"], profile["adherence"], profile["notes"]),
    )
    db.commit()
    return _one("SELECT * FROM clients WHERE id = ?", (cursor.lastrowid,))


def update_client(client_id: int, profile: Mapping[str, Any]) -> dict[str, Any]:
    db = get_db()
    db.execute(
        """
        UPDATE clients
           SET name = ?, age = ?, weight_kg = ?, program = ?, calories = ?,
               adherence = ?, notes = ?
         WHERE id = ?
        """,
        (profile["name"], profile["age"], profile["weight_kg"], profile["program"],
         profile["calories"], profile["adherence"], profile["notes"], client_id),
    )
    db.commit()
    return _one("SELECT * FROM clients WHERE id = ?", (client_id,))


# ----------------------------------------------------------------- progress


def insert_progress(client_id: int, week: str, adherence: int) -> dict[str, Any]:
    db = get_db()
    cursor = db.execute(
        "INSERT INTO progress (client_id, week, adherence) VALUES (?, ?, ?)",
        (client_id, week, adherence),
    )
    db.commit()
    return _one("SELECT * FROM progress WHERE id = ?", (cursor.lastrowid,))


def list_progress(client_id: int) -> list[dict[str, Any]]:
    return _all("SELECT * FROM progress WHERE client_id = ? ORDER BY id", (client_id,))
