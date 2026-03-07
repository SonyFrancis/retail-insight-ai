from typing import TypedDict

class InsightState(TypedDict):
    metrics: dict
    insight: str
    approved: bool
    retry_count: int