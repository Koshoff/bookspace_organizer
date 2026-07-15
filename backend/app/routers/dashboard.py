"""
Начално табло — обобщени показатели над db.dashboard.
Защитено: изисква валидна сесия.
"""
from fastapi import APIRouter, Depends, Query

import db
from app.deps import get_current_operator

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("")
def dashboard(
    date_from: str = Query(..., description="ГГГГ-ММ-ДД"),
    date_to: str = Query(..., description="ГГГГ-ММ-ДД"),
    payment_method: str | None = Query(default=None),
    operator: dict = Depends(get_current_operator),
):
    return db.get_dashboard_data(date_from, date_to, payment_method)
