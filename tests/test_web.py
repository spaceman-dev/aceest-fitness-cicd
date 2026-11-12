"""Dashboard pages and app wiring."""

from __future__ import annotations

import importlib

from flask import Flask

from aceest import __version__, create_app
from aceest.config import DevelopmentConfig, ProductionConfig, TestingConfig, get_config


def test_dashboard_lists_programs_and_site_metrics(client):
    response = client.get("/")
    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "ACEest FUNCTIONAL FITNESS" in page
    assert "Select a program to view the workout" in page
    assert "CAPACITY: 150 Users" in page
    assert "AREA: 10,000 sq ft" in page


def test_selecting_a_program_shows_its_charts(client):
    page = client.get("/?program=MG").get_data(as_text=True)
    assert "Deadlift 4x6" in page
    assert "Chicken Biryani" in page
    assert "Select a program to view the workout" not in page


def test_selecting_an_unknown_program_is_a_404_page(client):
    response = client.get("/?program=XYZ")
    assert response.status_code == 404
    assert not response.is_json


def test_footer_shows_version_and_track(client):
    page = client.get("/").get_data(as_text=True)
    assert f"v{__version__}" in page
    assert "&middot; test" in page


def test_stylesheet_is_served(client):
    assert client.get("/static/css/style.css").status_code == 200


def test_named_configs_resolve():
    assert get_config("development") is DevelopmentConfig
    assert get_config("testing") is TestingConfig
    assert get_config("production") is ProductionConfig
    assert get_config("anything-else") is ProductionConfig


def test_factory_applies_overrides():
    app = create_app("testing", overrides={"TRACK": "canary"})
    assert app.config["TESTING"] is True
    assert app.config["TRACK"] == "canary"


def test_wsgi_entrypoint_exposes_an_app():
    module = importlib.import_module("ACEest_Fitness")
    assert isinstance(module.app, Flask)


def test_profile_form_shows_the_calorie_estimate_and_plan(client):
    response = client.post("/profile", data={
        "name": "Meera Nair", "age": "28", "weight_kg": "58", "program": "FL", "adherence": "70",
    })
    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "Client Meera Nair saved successfully. Adherence: 70%" in page
    assert "Estimated Calories: 1276 kcal" in page  # 58 kg x 22
    assert "Zone 2 Cardio 30min" in page


def test_invalid_profile_is_rejected_with_the_reason(client):
    response = client.post("/profile", data={
        "name": "Meera Nair", "age": "28", "weight_kg": "five", "program": "FL",
    })
    assert response.status_code == 400
    assert "&#39;weight_kg&#39; must be a number" in response.get_data(as_text=True)


def test_forms_carry_a_csrf_token(csrf_client):
    assert 'name="csrf_token"' in csrf_client.get("/login").get_data(as_text=True)


def test_form_post_without_csrf_token_is_refused(csrf_client):
    response = csrf_client.post("/profile", data={
        "name": "Meera Nair", "age": "28", "weight_kg": "58", "program": "FL",
    })
    assert response.status_code == 400


def test_json_api_does_not_need_a_csrf_token(csrf_client):
    response = csrf_client.post("/api/calories", json={"weight_kg": 80, "program": "MG"})
    assert response.status_code == 200
