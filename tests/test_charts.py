"""SVG chart rendering and the progress chart endpoint."""

from __future__ import annotations

import xml.etree.ElementTree as ET

from aceest.charts import line_chart

SVG = "{http://www.w3.org/2000/svg}"


def test_chart_is_valid_svg_with_one_marker_per_point():
    root = ET.fromstring(line_chart("Adherence", [("2026-W44", 60), ("2026-W45", 80), ("2026-W46", 95)]))
    assert root.tag == f"{SVG}svg"
    assert len(root.findall(f"{SVG}circle")) == 3
    assert len(root.find(f"{SVG}polyline").get("points").split()) == 3


def test_values_are_plotted_on_a_0_to_100_axis():
    root = ET.fromstring(line_chart("t", [("a", 0), ("b", 100), ("c", 250)]))
    ys = [float(c.get("cy")) for c in root.findall(f"{SVG}circle")]
    assert ys[0] > ys[1]          # 0% sits lower than 100%
    assert ys[2] == ys[1]         # values above the axis are clamped


def test_single_point_is_centred():
    root = ET.fromstring(line_chart("t", [("only", 50)]))
    assert float(root.find(f"{SVG}circle").get("cx")) == 44 + (640 - 44 - 16) / 2


def test_empty_chart_says_so():
    assert "No data yet" in line_chart("t", [])


def test_text_is_escaped():
    svg = line_chart("<script>alert(1)</script>", [("<b>", 10)])
    assert "<script>" not in svg
    assert "&lt;script&gt;" in svg
    ET.fromstring(svg)


def test_progress_chart_endpoint(client, enrolled):
    client.post("/api/clients/Ravi Kumar/progress", json={"week": "2026-W45", "adherence": 80})
    response = client.get("/api/clients/Ravi Kumar/progress/chart.svg")
    assert response.status_code == 200
    assert response.mimetype == "image/svg+xml"
    assert "Weekly adherence - Ravi Kumar" in response.get_data(as_text=True)


def test_progress_chart_for_unknown_client_is_a_404(client):
    assert client.get("/api/clients/Ghost/progress/chart.svg").status_code == 404


def test_client_page_embeds_the_chart(client, enrolled):
    page = client.get("/clients/Ravi Kumar").get_data(as_text=True)
    assert "/api/clients/Ravi%20Kumar/progress/chart.svg" in page
