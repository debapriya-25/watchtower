"""Alert service: persistence, ownership enforcement and evaluation logic.

Ownership is enforced via :func:`_get_owned_alert` (404 if missing, 403 if owned
by another user). :func:`evaluate_alert` holds the pure trigger logic; there is
no scheduler/worker in this phase — callers (e.g. a future background job)
supply the current price.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, PermissionDeniedError
from app.core.logging import get_logger
from app.models.alert import Alert
from app.models.enums import AlertCondition
from app.models.token import Token
from app.models.user import User

logger = get_logger(__name__)


# --------------------------------------------------------------------------- #
# Ownership-guarded lookups
# --------------------------------------------------------------------------- #
async def _get_owned_alert(
    db: AsyncSession, user: User, alert_id: uuid.UUID
) -> Alert:
    """Return the alert if it exists and is owned by ``user`` (404 / 403)."""
    alert = await db.get(Alert, alert_id)
    if alert is None:
        raise NotFoundError("Alert not found.")
    if alert.user_id != user.id:
        logger.warning(
            "alert_ownership_denied",
            user_id=str(user.id),
            alert_id=str(alert_id),
            owner_id=str(alert.user_id),
        )
        raise PermissionDeniedError("You do not have access to this alert.")
    return alert


async def _load(db: AsyncSession, alert_id: uuid.UUID) -> Alert:
    """Reload an alert with its token eagerly loaded (for responses)."""
    result = await db.execute(
        select(Alert)
        .where(Alert.id == alert_id)
        .options(selectinload(Alert.token))
    )
    return result.scalar_one()


# --------------------------------------------------------------------------- #
# CRUD
# --------------------------------------------------------------------------- #
async def create_alert(
    db: AsyncSession,
    user: User,
    *,
    token_id: uuid.UUID,
    condition: AlertCondition,
    target_price: float,
) -> Alert:
    """Create an alert for ``user``; 404 if the token does not exist.

    ``target_price > 0`` is enforced by the request schema.
    """
    token = await db.get(Token, token_id)
    if token is None:
        raise NotFoundError("Token not found.")

    alert = Alert(
        user_id=user.id,
        token_id=token_id,
        condition=condition,
        target_price=Decimal(str(target_price)),
        is_active=True,
    )
    db.add(alert)
    await db.flush()
    logger.info(
        "alert_created",
        user_id=str(user.id),
        alert_id=str(alert.id),
        token_id=str(token_id),
    )
    return await _load(db, alert.id)


async def list_alerts(db: AsyncSession, user: User) -> list[Alert]:
    """Return the caller's alerts (newest first), with tokens loaded."""
    result = await db.execute(
        select(Alert)
        .where(Alert.user_id == user.id)
        .options(selectinload(Alert.token))
        .order_by(Alert.created_at.desc())
    )
    return list(result.scalars().all())


async def count_alerts(db: AsyncSession, user: User) -> int:
    return int(
        await db.scalar(
            select(func.count()).select_from(Alert).where(Alert.user_id == user.id)
        )
        or 0
    )


async def get_alert(
    db: AsyncSession, user: User, alert_id: uuid.UUID
) -> Alert:
    await _get_owned_alert(db, user, alert_id)
    return await _load(db, alert_id)


async def update_alert(
    db: AsyncSession,
    user: User,
    alert_id: uuid.UUID,
    *,
    fields: dict,
) -> Alert:
    """Update an owned alert's ``condition`` / ``target_price``."""
    alert = await _get_owned_alert(db, user, alert_id)

    if fields.get("condition") is not None:
        alert.condition = fields["condition"]
    if fields.get("target_price") is not None:
        alert.target_price = Decimal(str(fields["target_price"]))

    await db.flush()
    logger.info("alert_updated", alert_id=str(alert_id))
    return await _load(db, alert_id)


async def delete_alert(
    db: AsyncSession, user: User, alert_id: uuid.UUID
) -> None:
    alert = await _get_owned_alert(db, user, alert_id)
    await db.delete(alert)
    await db.flush()
    logger.info("alert_deleted", alert_id=str(alert_id))


async def set_active(
    db: AsyncSession, user: User, alert_id: uuid.UUID, *, active: bool
) -> Alert:
    """Activate or deactivate an owned alert.

    Activating re-arms the alert (clears ``triggered_at``) so it can fire again.
    """
    alert = await _get_owned_alert(db, user, alert_id)
    alert.is_active = active
    if active:
        alert.triggered_at = None
    await db.flush()
    logger.info("alert_active_set", alert_id=str(alert_id), is_active=active)
    return await _load(db, alert_id)


# --------------------------------------------------------------------------- #
# Evaluation (pure logic — no scheduler/worker in this phase)
# --------------------------------------------------------------------------- #
def evaluate_alert(alert: Alert, current_price: float | Decimal) -> bool:
    """Evaluate an alert against the current price.

    Trigger rules:
      * ``ABOVE`` → ``current_price >= target_price``
      * ``BELOW`` → ``current_price <= target_price``

    On a trigger the alert is mutated in place: ``triggered_at`` is stamped and
    ``is_active`` is set to ``False`` (one-shot). Already-inactive alerts never
    trigger. Returns ``True`` iff the alert fired on this evaluation.
    """
    if not alert.is_active:
        return False

    price = Decimal(str(current_price))
    if alert.condition == AlertCondition.ABOVE:
        triggered = price >= alert.target_price
    else:  # AlertCondition.BELOW
        triggered = price <= alert.target_price

    if triggered:
        alert.triggered_at = datetime.now(timezone.utc)
        alert.is_active = False
        logger.info(
            "alert_triggered",
            alert_id=str(alert.id),
            condition=alert.condition.value,
            target_price=str(alert.target_price),
            current_price=str(price),
        )

    return triggered
