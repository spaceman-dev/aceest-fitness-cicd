"""Membership plans, renewals and payments, and training templates (3.2.4)."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from aceest import services
from aceest.errors import ValidationError
from aceest.membership import PLANS, renewal
from aceest.programs import templates_for

TODAY = date(2026, 11, 12)


@pytest.mark.parametrize(("current_end", "plan", "start", "end"), [
    (None, "monthly", "2026-11-12", "2026-12-11"),
    ("2026-11-01", "monthly", "2026-11-12", "2026-12-11"),    # lapsed: starts today
    ("2026-11-20", "quarterly", "2026-11-21", "2027-02-18"),  # early: keeps the 8 days left
    ("2026-11-12", "annual", "2026-11-13", "2027-11-12"),
])
def test_renewal_periods(current_end, plan, start, end):
    payment = renewal(current_end, {"plan": plan, "method": "card"}, TODAY)
    assert (payment["period_start"], payment["period_end"]) == (start, end)
    assert payment["amount_inr"] == PLANS[plan]["fee_inr"]
    assert payment["method"] == "Card"
    assert payment["paid_on"] == "2026-11-12"


@pytest.mark.parametrize(("payload", "field"), [({"plan": "weekly"}, "plan"),
                                                ({"plan": "monthly", "method": "cheque"}, "method")])
def test_renewal_validation(payload, field):
    with pytest.raises(ValidationError) as excinfo:
        renewal(None, payload, TODAY)
    assert excinfo.value.field == field


def test_method_defaults_to_upi():
    assert renewal(None, {"plan": "monthly"}, TODAY)["method"] == "UPI"


def test_expiring_soon_is_filtered_and_sorted():
    clients = [
        {"name": "Later", "membership_end": "2026-11-30"},
        {"name": "Soon", "membership_end": "2026-11-15"},
        {"name": "Gone", "membership_end": "2026-11-01"},
        {"name": "Fine", "membership_end": "2027-06-01"},
        {"name": "Unset", "membership_end": None},
    ]
    assert [c["name"] for c in services.expiring_soon(clients, TODAY)] == ["Soon"]


def test_templates_follow_the_program():
    assert templates_for("fl") == ("Full Body HIIT", "Circuit Training", "Cardio + Weights")
    assert templates_for("nope") == ()
    assert services.validate_template("MG", "upper/lower split") == "Upper/Lower Split"
    assert services.validate_template("MG", "") is None
    with pytest.raises(ValidationError):
        services.validate_template("BG", "Push/Pull/Legs")


def test_plans_are_public(anon_client):
    body = anon_client.get("/api/membership/plans").get_json()
    assert [p["code"] for p in body["plans"]] == ["monthly", "quarterly", "annual"]
    assert body["methods"] == ["Cash", "Card", "UPI"]


def test_renew_through_the_api(client, enrolled):
    response = client.post("/api/clients/Ravi Kumar/membership/renew",
                           json={"plan": "quarterly", "method": "UPI"})
    assert response.status_code == 201
    body = response.get_json()
    assert body["payment"]["recorded_by"] == "admin"
    assert body["membership_status"] == "Active"

    membership = client.get("/api/clients/Ravi Kumar/membership").get_json()
    assert membership["membership_end"] == body["payment"]["period_end"]
    assert len(membership["payments"]) == 1
    assert client.post("/api/clients/Ravi Kumar/membership/renew",
                       json={"plan": "fortnightly"}).status_code == 400


def test_expiring_list_needs_sign_in(anon_client, client, profile_payload):
    soon = (date.today() + timedelta(days=5)).isoformat()
    client.post("/api/clients", json={**profile_payload, "membership_end": soon})
    assert anon_client.get("/api/memberships/expiring").status_code == 401
    listed = client.get("/api/memberships/expiring").get_json()["clients"]
    assert listed == [{"name": "Ravi Kumar", "membership_end": soon, "days_left": 5}]
    assert "Memberships ending in the next 14 days" in client.get("/").get_data(as_text=True)
    assert f"<td>{soon}</td>" in client.get("/").get_data(as_text=True)


def test_template_through_the_api(client, enrolled):
    assert client.put("/api/clients/Ravi Kumar/template",
                      json={"template": "push/pull/legs"}).get_json()["template"] == "Push/Pull/Legs"
    assert client.get("/api/clients/Ravi Kumar").get_json()["template"] == "Push/Pull/Legs"
    assert client.put("/api/clients/Ravi Kumar/template",
                      json={"template": "Circuit Training"}).status_code == 400


class TestPages:
    def test_renew_form(self, client, enrolled):
        page = client.post("/clients/Ravi Kumar/membership", data={"plan": "monthly", "method": "Cash"},
                           follow_redirects=True).get_data(as_text=True)
        assert "Membership renewed until" in page
        assert "INR 2,500 (Cash)" in page

    def test_bad_renewal_is_flashed(self, client, enrolled):
        page = client.post("/clients/Ravi Kumar/membership", data={"plan": "lifetime"},
                           follow_redirects=True).get_data(as_text=True)
        assert "&#39;plan&#39; must be one of" in page

    def test_template_form(self, client, enrolled):
        page = client.post("/clients/Ravi Kumar/template", data={"template": "Full Body Strength"},
                           follow_redirects=True).get_data(as_text=True)
        assert "Training template set to Full Body Strength" in page
        assert "Template  : Full Body Strength" in page
        cleared = client.post("/clients/Ravi Kumar/template", data={"template": ""},
                              follow_redirects=True).get_data(as_text=True)
        assert "Training template cleared" in cleared

    def test_bad_template_is_flashed(self, client, enrolled):
        page = client.post("/clients/Ravi Kumar/template", data={"template": "Yoga"},
                           follow_redirects=True).get_data(as_text=True)
        assert "&#39;template&#39; must be one of" in page
