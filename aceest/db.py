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
    (2, [
        # 2.1.2: one entry per client and week - keep the latest of any duplicates
        """
        DELETE FROM progress
         WHERE id NOT IN (SELECT MAX(id) FROM progress GROUP BY client_id, week)
        """,
        "CREATE UNIQUE INDEX IF NOT EXISTS progress_client_week ON progress (client_id, week)",
    ]),
    (3, [
        # 2.2.4: height and goals, the FL3/FL5 split, workouts and body metrics.
        # Only additive changes, so a 2.2.1 replica still runs against this schema.
        "ALTER TABLE clients ADD COLUMN height_cm REAL",
        "ALTER TABLE clients ADD COLUMN target_weight_kg REAL",
        "ALTER TABLE clients ADD COLUMN target_adherence INTEGER",
        "UPDATE clients SET program = 'FL3' WHERE program = 'FL'",
        """
        CREATE TABLE IF NOT EXISTS workouts (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id    INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
            date         TEXT    NOT NULL,
            workout_type TEXT    NOT NULL,
            duration_min INTEGER NOT NULL,
            notes        TEXT    NOT NULL DEFAULT ''
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS exercises (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            workout_id INTEGER NOT NULL REFERENCES workouts(id) ON DELETE CASCADE,
            name       TEXT    NOT NULL,
            sets       INTEGER NOT NULL,
            reps       INTEGER NOT NULL,
            weight_kg  REAL    NOT NULL DEFAULT 0
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS metrics (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id   INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
            date        TEXT    NOT NULL,
            weight_kg   REAL,
            waist_cm    REAL,
            bodyfat_pct REAL
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
        # WAL lets readers on other replicas carry on while one of them writes;
        # the setting is stored in the database file itself.
        connection.execute("PRAGMA journal_mode=WAL")
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


CLIENT_FIELDS = ("name", "age", "height_cm", "weight_kg", "program", "calories", "adherence",
                 "notes", "target_weight_kg", "target_adherence")


def _client_values(profile: Mapping[str, Any]) -> tuple[Any, ...]:
    return tuple(profile.get(field) for field in CLIENT_FIELDS)


def insert_client(profile: Mapping[str, Any]) -> dict[str, Any]:
    db = get_db()
    cursor = db.execute(
        """
        INSERT INTO clients (name, age, height_cm, weight_kg, program, calories, adherence,
                             notes, target_weight_kg, target_adherence)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        _client_values(profile),
    )
    db.commit()
    return _one("SELECT * FROM clients WHERE id = ?", (cursor.lastrowid,))


def update_client(client_id: int, profile: Mapping[str, Any]) -> dict[str, Any]:
    db = get_db()
    db.execute(
        """
        UPDATE clients
           SET name = ?, age = ?, height_cm = ?, weight_kg = ?, program = ?, calories = ?,
               adherence = ?, notes = ?, target_weight_kg = ?, target_adherence = ?
         WHERE id = ?
        """,
        (*_client_values(profile), client_id),
    )
    db.commit()
    return _one("SELECT * FROM clients WHERE id = ?", (client_id,))


# ----------------------------------------------------------------- progress


def save_progress(client_id: int, week: str, adherence: int) -> dict[str, Any]:
    """Record a week's adherence; logging the same week again replaces it."""
    db = get_db()
    db.execute(
        """
        INSERT INTO progress (client_id, week, adherence) VALUES (?, ?, ?)
        ON CONFLICT (client_id, week)
        DO UPDATE SET adherence = excluded.adherence, logged_at = datetime('now')
        """,
        (client_id, week, adherence),
    )
    db.commit()
    return _one("SELECT * FROM progress WHERE client_id = ? AND week = ?", (client_id, week))


def list_progress(client_id: int) -> list[dict[str, Any]]:
    return _all("SELECT * FROM progress WHERE client_id = ? ORDER BY week", (client_id,))


# ----------------------------------------------------------------- workouts


def insert_workout(client_id: int, workout: Mapping[str, Any]) -> dict[str, Any]:
    """Store a session and its exercises in one transaction."""
    db = get_db()
    with db:
        cursor = db.execute(
            "INSERT INTO workouts (client_id, date, workout_type, duration_min, notes) "
            "VALUES (?, ?, ?, ?, ?)",
            (client_id, workout["date"], workout["workout_type"], workout["duration_min"],
             workout["notes"]),
        )
        workout_id = cursor.lastrowid
        db.executemany(
            "INSERT INTO exercises (workout_id, name, sets, reps, weight_kg) "
            "VALUES (?, ?, ?, ?, ?)",
            [(workout_id, e["name"], e["sets"], e["reps"], e["weight_kg"])
             for e in workout["exercises"]],
        )
    saved = _one("SELECT * FROM workouts WHERE id = ?", (workout_id,))
    saved["exercises"] = _all("SELECT name, sets, reps, weight_kg FROM exercises "
                              "WHERE workout_id = ? ORDER BY id", (workout_id,))
    return saved


def list_workouts(client_id: int) -> list[dict[str, Any]]:
    workouts = _all("SELECT * FROM workouts WHERE client_id = ? ORDER BY date DESC, id DESC",
                    (client_id,))
    for workout in workouts:
        workout["exercises"] = _all("SELECT name, sets, reps, weight_kg FROM exercises "
                                    "WHERE workout_id = ? ORDER BY id", (workout["id"],))
    return workouts


# ------------------------------------------------------------------ metrics


def insert_metrics(client_id: int, entry: Mapping[str, Any]) -> dict[str, Any]:
    db = get_db()
    cursor = db.execute(
        "INSERT INTO metrics (client_id, date, weight_kg, waist_cm, bodyfat_pct) "
        "VALUES (?, ?, ?, ?, ?)",
        (client_id, entry["date"], entry["weight_kg"], entry["waist_cm"], entry["bodyfat_pct"]),
    )
    db.commit()
    return _one("SELECT * FROM metrics WHERE id = ?", (cursor.lastrowid,))


def list_metrics(client_id: int) -> list[dict[str, Any]]:
    return _all("SELECT * FROM metrics WHERE client_id = ? ORDER BY date, id", (client_id,))
