"""Membership plans and renewals.

Aceestver-3.2.4 shows a membership status and renewal date per client; here
the date is driven by recorded payments. A renewal extends the membership
from whichever is later - today or the current end date - so paying early
never loses the remaining days.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, timedelta
from typing import Any

from .errors import ValidationError

PLANS: dict[str, dict[str, Any]] = {
    "monthly": {"code": "monthly", "name": "Monthly", "days": 30, "fee_inr": 2500},
    "quarterly": {"code": "quarterly", "name": "Quarterly", "days": 90, "fee_inr": 6500},
    "annual": {"code": "annual", "name": "Annual", "days": 365, "fee_inr": 24000},
}

PAYMENT_METHODS = ("Cash", "Card", "UPI")


def list_plans() -> list[dict[str, Any]]:
    return list(PLANS.values())


def validate_plan(value: Any) -> dict[str, Any]:
    plan = PLANS.get(str(value or "").strip().lower())
    if plan is None:
        raise ValidationError(f"'plan' must be one of {', '.join(PLANS)}", field="plan")
    return plan


def validate_method(value: Any) -> str:
    for method in PAYMENT_METHODS:
        if str(value or "").strip().lower() == method.lower():
            return method
    raise ValidationError(f"'method' must be one of {', '.join(PAYMENT_METHODS)}", field="method")


def renewal(current_end: str | None, payload: Mapping[str, Any],
            today: date | None = None) -> dict[str, Any]:
    """Work out the new period and the payment record for a renewal."""
    plan = validate_plan(payload.get("plan"))
    method = validate_method(payload.get("method") or "UPI")
    today = today or date.today()
    start = today
    if current_end and date.fromisoformat(current_end) >= today:
        start = date.fromisoformat(current_end) + timedelta(days=1)
    end = start + timedelta(days=plan["days"] - 1)
    return {
        "plan": plan["code"],
        "amount_inr": plan["fee_inr"],
        "method": method,
        "period_start": start.isoformat(),
        "period_end": end.isoformat(),
        "paid_on": today.isoformat(),
    }
