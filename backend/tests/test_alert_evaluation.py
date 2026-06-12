"""Pure unit tests for ``evaluate_alert`` (no DB / no event loop).

Covers ABOVE/BELOW triggering, the inclusive boundary, the no-trigger path, and
the one-shot auto-disable behaviour.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from app.models.alert import Alert
from app.models.enums import AlertCondition
from app.services.alert_service import evaluate_alert


def _alert(condition: AlertCondition, target: str) -> Alert:
    """Build an in-memory alert (not persisted) for evaluation tests."""
    return Alert(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        token_id=uuid.uuid4(),
        condition=condition,
        target_price=Decimal(target),
        is_active=True,
        triggered_at=None,
    )


def test_above_trigger():
    alert = _alert(AlertCondition.ABOVE, "100")
    assert evaluate_alert(alert, 150) is True
    assert alert.is_active is False
    assert isinstance(alert.triggered_at, datetime)
    assert alert.triggered_at.tzinfo is not None  # timezone-aware


def test_above_no_trigger():
    alert = _alert(AlertCondition.ABOVE, "100")
    assert evaluate_alert(alert, 99.99) is False
    assert alert.is_active is True
    assert alert.triggered_at is None


def test_below_trigger():
    alert = _alert(AlertCondition.BELOW, "100")
    assert evaluate_alert(alert, 50) is True
    assert alert.is_active is False
    assert alert.triggered_at is not None


def test_below_no_trigger():
    alert = _alert(AlertCondition.BELOW, "100")
    assert evaluate_alert(alert, 100.01) is False
    assert alert.is_active is True


def test_boundary_is_inclusive():
    # ABOVE uses >=, BELOW uses <= — exact equality triggers.
    assert evaluate_alert(_alert(AlertCondition.ABOVE, "100"), 100) is True
    assert evaluate_alert(_alert(AlertCondition.BELOW, "100"), 100) is True


def test_auto_disable_after_trigger():
    alert = _alert(AlertCondition.ABOVE, "100")
    # First crossing fires and disables the alert.
    assert evaluate_alert(alert, 120) is True
    assert alert.is_active is False
    triggered_first = alert.triggered_at
    # A second evaluation must NOT re-trigger an already-inactive alert.
    assert evaluate_alert(alert, 200) is False
    assert alert.triggered_at == triggered_first
