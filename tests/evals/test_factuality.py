import pytest
from app.evals.factuality import run_factuality_eval

# ── Golden fixtures ───────────────────────────────────────────────────

METRICS_CLEAN = {
    "trend_results": [
        {
            "type": "trend", "metric": "revenue",
            "entity": {"category": "Electronics"},
            "direction": "increase",
            "pct_change": 14.31,
            "weekly_slope": 120.5,
            "p_value": 0.002,
            "time_window": "2024-W01 → 2024-W12",
        },
        {
            "type": "trend", "metric": "revenue",
            "entity": {"category": "Fashion"},
            "direction": "decrease",
            "pct_change": -10.59,
            "weekly_slope": -88.2,
            "p_value": 0.01,
            "time_window": "2024-W01 → 2024-W12",
        },
    ],
    "anomalies_detected": [
        {
            "type": "anomaly", "metric": "revenue",
            "entity": {"category": "Electronics"},
            "week": "2024-W38", "value": 95000.0, "z_score": 2.8,
        }
    ],
    "contribution_analysis": [
        {
            "type": "contribution", "metric": "revenue",
            "entity": {"category": "Electronics"},
            "week_comparison": "2024-W11 → 2024-W12",
            "delta_value": 12000.0, "contribution_pct": 48.15,
        }
    ],
    "row_count": 500,
}

# ── Test cases ────────────────────────────────────────────────────────

def test_accurate_insight_passes():
    insight = {
        "trend_insights": (
            "Electronics revenue increased by 14.31% with a strong upward slope, "
            "while Fashion revenue declined by 10.59%."
        ),
        "anomaly_insights": "Anomalies were detected in Electronics during week 38.",
        "contribution_insights": "Electronics contributed 48.15% of recent revenue growth.",
        "confidence": "high",
    }
    report = run_factuality_eval(insight, METRICS_CLEAN)
    for r in report.results:                                          # ← ADD
        print(f"[{'PASS' if r.passed else 'FAIL'}] {r.check_type} | {r.claim_text} | {r.note}")  # ← ADD
    assert report.verdict == "pass", report.summary()

def test_hallucinated_percentage_fails():
    insight = {
        "trend_insights": "Electronics revenue increased by 45.0%.",  # invented number
        "anomaly_insights": "No significant anomalies detected.",
        "contribution_insights": "No major contribution changes detected.",
        "confidence": "medium",
    }
    report = run_factuality_eval(insight, METRICS_CLEAN)
    numeric_results = [r for r in report.results if r.check_type == "numeric"]
    assert any(not r.passed for r in numeric_results), "Should flag hallucinated 45%"


def test_inverted_direction_fails():
    insight = {
        "trend_insights": "Electronics revenue decreased by 14.31%.",  # wrong direction
        "anomaly_insights": "No significant anomalies detected.",
        "contribution_insights": "No major contribution changes detected.",
        "confidence": "low",
    }
    report = run_factuality_eval(insight, METRICS_CLEAN)
    direction_results = [r for r in report.results if r.check_type == "direction"]
    assert any(not r.passed for r in direction_results), "Should flag inverted direction"


def test_hallucinated_entity_fails():
    insight = {
        "trend_insights": "Automotive revenue increased by 14.31%.",  # entity not in data
        "anomaly_insights": "No significant anomalies detected.",
        "contribution_insights": "No major contribution changes detected.",
        "confidence": "medium",
    }
    report = run_factuality_eval(insight, METRICS_CLEAN)
    entity_results = [r for r in report.results if r.check_type == "entity"]
    assert any(not r.passed for r in entity_results), "Should flag unknown entity"


def test_empty_insight_passes_gracefully():
    insight = {
        "trend_insights": "No significant trend detected.",
        "anomaly_insights": "No significant anomalies detected.",
        "contribution_insights": "No major contribution changes detected.",
        "confidence": "low",
    }
    report = run_factuality_eval(insight, METRICS_CLEAN)
    # No numeric claims → no numeric failures → should pass
    assert report.verdict in ("pass", "warn")