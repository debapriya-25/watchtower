"""Price-alert routes (``/api/v1/alerts``).

All routes require authentication and are strictly **owner-scoped**: a user can
only access their own alerts (others return 403). Notification delivery is out of
scope for this phase — these endpoints manage alert definitions and their
active/triggered state only.

* ``POST   /api/v1/alerts``                  — create an alert
* ``GET    /api/v1/alerts``                  — list my alerts
* ``GET    /api/v1/alerts/{id}``             — retrieve one
* ``PATCH  /api/v1/alerts/{id}``             — update condition/target price
* ``DELETE /api/v1/alerts/{id}``             — delete
* ``POST   /api/v1/alerts/{id}/activate``    — re-arm (is_active=true)
* ``POST   /api/v1/alerts/{id}/deactivate``  — disable (is_active=false)
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Path, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.responses import success_response
from app.db.session import get_db
from app.deps.auth import CurrentUser
from app.schemas.alert import AlertCreate, AlertList, AlertPublic, AlertUpdate
from app.schemas.common import Envelope, ErrorEnvelope, MessageData
from app.services import alert_service

router = APIRouter(prefix="/api/v1/alerts", tags=["alerts"])

DbSession = Annotated[AsyncSession, Depends(get_db)]
AlertIdPath = Annotated[uuid.UUID, Path(description="Alert id")]

_AUTH_RESPONSES = {
    401: {"model": ErrorEnvelope, "description": "Authentication required"},
}
_OWNED_RESPONSES = {
    **_AUTH_RESPONSES,
    403: {"model": ErrorEnvelope, "description": "Alert belongs to another user"},
    404: {"model": ErrorEnvelope, "description": "Alert not found"},
}


def _public(alert) -> dict:
    return AlertPublic.model_validate(alert).model_dump()


@router.post(
    "",
    response_model=Envelope[AlertPublic],
    status_code=status.HTTP_201_CREATED,
    summary="Create a price alert",
    description="Creates an alert that triggers when the token's price crosses "
    "`target_price` in the given direction. The token must exist in the "
    "catalogue (404 otherwise) and `target_price` must be > 0 (422 otherwise). "
    "New alerts start active and un-triggered.",
    responses={
        **_AUTH_RESPONSES,
        404: {"model": ErrorEnvelope, "description": "Token not found"},
        422: {"model": ErrorEnvelope, "description": "Invalid target price"},
    },
)
async def create_alert(
    current_user: CurrentUser,
    db: DbSession,
    payload: AlertCreate,
) -> JSONResponse:
    alert = await alert_service.create_alert(
        db,
        current_user,
        token_id=payload.token_id,
        condition=payload.condition,
        target_price=payload.target_price,
    )
    return success_response(data=_public(alert), status_code=status.HTTP_201_CREATED)


@router.get(
    "",
    response_model=Envelope[AlertList],
    summary="List my alerts",
    description="Returns the current user's alerts (newest first). Never "
    "includes other users' alerts.",
    responses=_AUTH_RESPONSES,
)
async def list_alerts(
    current_user: CurrentUser,
    db: DbSession,
) -> JSONResponse:
    alerts = await alert_service.list_alerts(db, current_user)
    data = AlertList(
        items=[AlertPublic.model_validate(a) for a in alerts],
        total=len(alerts),
    )
    return success_response(data=data.model_dump())


@router.get(
    "/{alert_id}",
    response_model=Envelope[AlertPublic],
    summary="Get one of my alerts",
    description="Returns a single alert. 403 if it belongs to another user, "
    "404 if it does not exist.",
    responses=_OWNED_RESPONSES,
)
async def get_alert(
    current_user: CurrentUser,
    db: DbSession,
    alert_id: AlertIdPath,
) -> JSONResponse:
    alert = await alert_service.get_alert(db, current_user, alert_id)
    return success_response(data=_public(alert))


@router.patch(
    "/{alert_id}",
    response_model=Envelope[AlertPublic],
    summary="Update an alert",
    description="Updates an owned alert's `condition` and/or `target_price` "
    "(must stay > 0). Use activate/deactivate to toggle active state.",
    responses={
        **_OWNED_RESPONSES,
        422: {"model": ErrorEnvelope, "description": "Invalid target price"},
    },
)
async def update_alert(
    current_user: CurrentUser,
    db: DbSession,
    payload: AlertUpdate,
    alert_id: AlertIdPath,
) -> JSONResponse:
    alert = await alert_service.update_alert(
        db, current_user, alert_id, fields=payload.model_dump(exclude_unset=True)
    )
    return success_response(data=_public(alert))


@router.delete(
    "/{alert_id}",
    response_model=Envelope[MessageData],
    summary="Delete an alert",
    description="Deletes an owned alert. 403 for another user's alert.",
    responses=_OWNED_RESPONSES,
)
async def delete_alert(
    current_user: CurrentUser,
    db: DbSession,
    alert_id: AlertIdPath,
) -> JSONResponse:
    await alert_service.delete_alert(db, current_user, alert_id)
    return success_response(data={"message": "Alert deleted."})


@router.post(
    "/{alert_id}/activate",
    response_model=Envelope[AlertPublic],
    summary="Activate (re-arm) an alert",
    description="Sets `is_active=true` and clears `triggered_at` so the alert "
    "can fire again.",
    responses=_OWNED_RESPONSES,
)
async def activate_alert(
    current_user: CurrentUser,
    db: DbSession,
    alert_id: AlertIdPath,
) -> JSONResponse:
    alert = await alert_service.set_active(db, current_user, alert_id, active=True)
    return success_response(data=_public(alert))


@router.post(
    "/{alert_id}/deactivate",
    response_model=Envelope[AlertPublic],
    summary="Deactivate an alert",
    description="Sets `is_active=false`. The alert will not trigger until "
    "re-activated.",
    responses=_OWNED_RESPONSES,
)
async def deactivate_alert(
    current_user: CurrentUser,
    db: DbSession,
    alert_id: AlertIdPath,
) -> JSONResponse:
    alert = await alert_service.set_active(db, current_user, alert_id, active=False)
    return success_response(data=_public(alert))
