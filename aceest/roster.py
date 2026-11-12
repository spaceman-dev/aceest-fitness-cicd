"""In-memory client roster.

Aceestver1.1.2 kept its clients in a Python list for as long as the window
was open; this is the same idea per web process. SQLite replaces it in 2.0.1.
"""

from __future__ import annotations

import threading
from collections.abc import Mapping
from typing import Any

from .errors import ConflictError


class ClientRoster:
    def __init__(self) -> None:
        self._clients: list[dict[str, Any]] = []
        self._lock = threading.Lock()

    def add(self, profile: Mapping[str, Any]) -> dict[str, Any]:
        client = dict(profile)
        with self._lock:
            if any(c["name"].casefold() == client["name"].casefold() for c in self._clients):
                raise ConflictError(f"client '{client['name']}' already exists", field="name")
            self._clients.append(client)
        return dict(client)

    def all(self) -> list[dict[str, Any]]:
        with self._lock:
            return [dict(client) for client in self._clients]

    def __len__(self) -> int:
        with self._lock:
            return len(self._clients)
