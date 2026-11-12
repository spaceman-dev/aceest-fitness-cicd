"""Small server-side SVG charts (the desktop builds used matplotlib windows).

Plain SVG keeps the image dependency-free and lets the browser scale it.
Every piece of text is escaped because names come from user input.
"""

from __future__ import annotations

from collections.abc import Sequence

from markupsafe import escape

WIDTH, HEIGHT = 640, 260
LEFT, RIGHT, TOP, BOTTOM = 44, 16, 30, 40


def line_chart(title: str, points: Sequence[tuple[str, float]], y_max: float = 100.0,
               unit: str = "%", colour: str = "#d4af37") -> str:
    """Line chart of (label, value) pairs; values are drawn on a 0..y_max axis."""
    plot_w = WIDTH - LEFT - RIGHT
    plot_h = HEIGHT - TOP - BOTTOM
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WIDTH} {HEIGHT}" '
        f'role="img" aria-label="{escape(title)}">',
        f'<rect width="{WIDTH}" height="{HEIGHT}" fill="#1c1c1c"/>',
        f'<text x="{WIDTH // 2}" y="18" fill="#f2f2f2" font-size="13" '
        f'text-anchor="middle">{escape(title)}</text>',
    ]
    for step in range(0, 5):
        value = y_max * step / 4
        y = TOP + plot_h - plot_h * step / 4
        parts.append(f'<line x1="{LEFT}" y1="{y:.1f}" x2="{WIDTH - RIGHT}" y2="{y:.1f}" '
                     f'stroke="#333" stroke-width="1"/>')
        parts.append(f'<text x="{LEFT - 6}" y="{y + 4:.1f}" fill="#9a9a9a" font-size="10" '
                     f'text-anchor="end">{value:g}{escape(unit)}</text>')

    if not points:
        parts.append(f'<text x="{WIDTH // 2}" y="{HEIGHT // 2}" fill="#9a9a9a" font-size="12" '
                     f'text-anchor="middle">No data yet</text>')
    else:
        gap = plot_w / max(len(points) - 1, 1)
        coords = []
        for index, (label, value) in enumerate(points):
            x = LEFT + (gap * index if len(points) > 1 else plot_w / 2)
            y = TOP + plot_h - plot_h * min(max(float(value), 0.0), y_max) / y_max
            coords.append((x, y, label, value))
        path = " ".join(f"{x:.1f},{y:.1f}" for x, y, _, _ in coords)
        parts.append(f'<polyline points="{path}" fill="none" stroke="{colour}" stroke-width="2"/>')
        for x, y, label, value in coords:
            parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.5" fill="{colour}">'
                         f'<title>{escape(label)}: {float(value):g}{escape(unit)}</title></circle>')
            parts.append(f'<text x="{x:.1f}" y="{HEIGHT - BOTTOM + 16}" fill="#9a9a9a" '
                         f'font-size="9" text-anchor="middle">{escape(label)}</text>')
    parts.append("</svg>")
    return "".join(parts)
