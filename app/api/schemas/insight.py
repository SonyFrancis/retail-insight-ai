from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class InsightRequest(BaseModel):
    partner_id: str
    metric:     str = "revenue"   # default, expandable for multi-KPI later

class InsightResponse(BaseModel):
    partner_id:            str
    trend_insights:        str
    anomaly_insights:      str
    contribution_insights: str
    confidence:            str
    generated_at:          datetime
    data_window:           str     # e.g. "May 2024 – Apr 2026"

class InsightDebugResponse(InsightResponse):
    factuality_score:   Optional[float] = None
    factuality_verdict: Optional[str]   = None
    llm_faithfulness:   Optional[float] = None   # ← Optional, not float
    llm_relevancy:      Optional[float] = None   # ← Optional, not float
    claim_results:      Optional[list[dict]] = None

class RefreshResponse(BaseModel):
    partner_id: str
    status:     str
    message:    str