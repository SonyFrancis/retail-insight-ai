from dataclasses import dataclass, field
from typing import Literal

@dataclass
class ClaimResult:
    claim_text: str
    check_type: Literal["numeric", "direction", "entity"]
    passed: bool
    stated_value: float | str | None
    actual_value: float | str | None
    note: str

@dataclass
class FactualityReport:
    overall_score: float          # 0.0 – 1.0
    verdict: Literal["pass", "warn", "fail"]
    total_claims: int
    passed_claims: int
    results: list[ClaimResult] = field(default_factory=list)

    def summary(self) -> str:
        return (
            f"[{self.verdict.upper()}] "
            f"Factuality {self.overall_score*100:.0f}% "
            f"({self.passed_claims}/{self.total_claims} claims passed)"
        )