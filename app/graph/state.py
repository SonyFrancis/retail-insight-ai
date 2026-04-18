from typing import TypedDict, Optional, Any

class InsightState(TypedDict):
    metrics: dict
    insight: str
    approved: bool
    retry_count: int
    factuality_report:  Optional[Any] 