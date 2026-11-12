"""PDF client report - the "Export PDF Report" button of Aceestver-3.1.2."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from fpdf import FPDF


def _text(value: Any) -> str:
    # the built-in PDF fonts only cover Latin-1
    return str("-" if value is None or value == "" else value).encode(
        "latin-1", "replace").decode("latin-1")


def client_report(client: Mapping[str, Any], summary: Mapping[str, Any],
                  workouts: Sequence[Mapping[str, Any]], generated_on: str) -> bytes:
    pdf = FPDF()
    pdf.set_title(_text(f"ACEest client report - {client['name']}"))
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, _text(f"Client Report - {client['name']}"), new_x="LMARGIN", new_y="NEXT",
             align="C")
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 6, _text(f"ACEest Fitness & Gym - generated {generated_on}"),
             new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.ln(6)

    rows = [
        ("Age", client.get("age")),
        ("Height", f"{_text(client.get('height_cm'))} cm"),
        ("Weight", f"{_text(client.get('weight_kg'))} kg"),
        ("Program", client.get("program_name")),
        ("Calories", f"{_text(client.get('calories'))} kcal/day"),
        ("BMI", f"{_text(client.get('bmi'))} {_text(client.get('category', ''))}".strip()),
        ("Target weight", f"{_text(client.get('target_weight_kg'))} kg"),
        ("Target adherence", f"{_text(client.get('target_adherence'))} %"),
        ("Membership", f"{_text(client.get('membership_status'))} "
                       f"(ends {_text(client.get('membership_end'))})"),
        ("Weeks logged", summary.get("weeks_logged")),
        ("Average adherence", f"{_text(summary.get('average_adherence'))} %"),
    ]
    pdf.set_font("Helvetica", "", 12)
    for label, value in rows:
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(55, 8, _text(label))
        pdf.set_font("Helvetica", "", 12)
        pdf.cell(0, 8, _text(value), new_x="LMARGIN", new_y="NEXT")

    pdf.ln(4)
    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(0, 8, "Recent workouts", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 11)
    if not workouts:
        pdf.cell(0, 7, "None logged", new_x="LMARGIN", new_y="NEXT")
    for workout in list(workouts)[:10]:
        pdf.cell(0, 7, _text(f"{workout['date']}  {workout['workout_type']}  "
                             f"{workout['duration_min']} min  {workout.get('notes', '')}"),
                 new_x="LMARGIN", new_y="NEXT")
    return bytes(pdf.output())
