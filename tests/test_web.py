"""Dashboard pages and app wiring."""

from __future__ import annotations

import importlib

from flask import Flask

from aceest import create_app
from aceest.config import DevelopmentConfig, ProductionConfig, TestingConfig, get_config


def test_dashboard_lists_programs_and_site_metrics(client):
    response = client.get("/")
    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "ACEest FUNCTIONAL FITNESS" in page
    assert "Select a profile to view workout" in page
    assert "CAPACITY: 150 Users" in page
    assert "AREA: 10,000 sq ft" in page


def test_selecting_a_program_shows_its_charts(client):
    page = client.get("/?program=MG").get_data(as_text=True)
    assert "Deadlift 4x6" in page
    assert "Chicken Biryani" in page
    assert "Select a profile to view workout" not in page


def test_selecting_an_unknown_program_is_a_404_page(client):
    response = client.get("/?program=XYZ")
    assert response.status_code == 404
    assert not response.is_json


def test_footer_shows_version_and_track(client):
    page = client.get("/").get_data(as_text=True)
    assert "v1.0.0" in page
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
