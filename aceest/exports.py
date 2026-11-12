"""CSV export of the client roster (the "Export CSV" button of Aceestver1.1.2)."""

from __future__ import annotations

import csv
import io
from collections.abc import Iterable, Mapping
from typing import Any

CSV_COLUMNS = ("Name", "Age", "Weight", "Program", "Adherence", "Notes", "Calories")

# Spreadsheet apps run a cell that starts like a formula, so free text is
# prefixed with a quote before it lands in the file.
_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def _text_cell(value: Any) -> str:
    text = "" if value is None else str(value)
    return "'" + text if text.startswith(_FORMULA_PREFIXES) else text


def clients_to_csv(clients: Iterable[Mapping[str, Any]]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(CSV_COLUMNS)
    for client in clients:
        writer.writerow([
            _text_cell(client["name"]),
            client["age"],
            client["weight_kg"],
            client["program"],
            client["adherence"],
            _text_cell(client.get("notes")),
            client["calories"],
        ])
    return buffer.getvalue()
