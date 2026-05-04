from fastapi import APIRouter, HTTPException
from app.api.schemas.insight import (
    InsightRequest, InsightResponse,
    InsightDebugResponse, RefreshResponse
)
from app.api.services.insight_service import generate_insight_for_partner
from app.db.crud import get_insight, list_partners

router = APIRouter(prefix="/insights", tags=["insights"])


@router.get("/{partner_id}", response_model=InsightResponse)
def get_partner_insight(partner_id: str):
    """
    Returns the latest stored insight for a partner.
    Account executives use this endpoint.
    """
    record = get_insight(partner_id)
    if record is None:
        raise HTTPException(
            status_code=404,
            detail=f"No insight found for {partner_id}. Run /insights/{partner_id}/refresh first."
        )
    return record


@router.get("/{partner_id}/debug", response_model=InsightDebugResponse)
def get_partner_insight_debug(partner_id: str):
    """
    Returns full eval detail for a partner insight.
    For operators and developers only.
    """
    record = get_insight(partner_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"No insight found for {partner_id}")
    return record


@router.post("/{partner_id}/refresh", response_model=RefreshResponse)
def refresh_partner_insight(partner_id: str):
    """
    Triggers fresh insight generation for a partner.
    Runs full pipeline and updates DB.
    """
    try:
        generate_insight_for_partner(partner_id)
        return RefreshResponse(
            partner_id=partner_id,
            status="success",
            message=f"Insight refreshed successfully for {partner_id}"
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/", response_model=list[str])
def list_available_partners():
    """Returns all partner IDs that have stored insights."""
    return list_partners()