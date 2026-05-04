import json
from datetime import datetime
from app.api.services.data import get_partner_data, load_sales_data
from app.insights.detectors import run_detectors, format_metrics_for_llm
from app.graph.builder import build_graph
from app.db.crud import upsert_insight

def run_llm_pipeline(partner_id: str, metrics: dict) -> dict:
    """
    Runs LangGraph + eval for one partner using pre-computed metrics.
    Used by both single refresh and batch precompute.
    """
    graph = build_graph()
    initial_state = {
        "metrics":           metrics,
        "insight":           None,
        "approved":          False,
        "retry_count":       0,
        "factuality_report": None,
        "llm_eval_result":   None,
    }
    result     = graph.invoke(initial_state)
    insight    = result.get("insight", {})
    report     = result.get("factuality_report")
    llm_eval   = result.get("llm_eval_result", {})
    confidence = report.compute_confidence() if report else "low"
    insight["confidence"] = confidence

    partner_df  = load_sales_data()
    partner_df  = partner_df[partner_df["partner_id"] == partner_id]
    dates       = partner_df["date"]
    data_window = f"{dates.min().strftime('%b %Y')} – {dates.max().strftime('%b %Y')}"

    record = {
        "partner_id":            partner_id,
        "trend_insights":        insight.get("trend_insights", ""),
        "anomaly_insights":      insight.get("anomaly_insights", ""),
        "contribution_insights": insight.get("contribution_insights", ""),
        "confidence":            confidence,
        "factuality_score":      report.overall_score if report else None,
        "factuality_verdict":    report.verdict if report else None,
        "llm_faithfulness":      llm_eval.get("faithfulness_score") if llm_eval else None,
        "llm_relevancy":         llm_eval.get("relevancy_score") if llm_eval else None,
        "claim_results":         json.dumps([
            {"claim_text": r.claim_text, "check_type": r.check_type,
             "passed": r.passed, "note": r.note}
            for r in (report.results if report else [])
        ]),
        "data_window":           data_window,
        "generated_at":          datetime.utcnow().isoformat(),
    }
    upsert_insight(record)
    return record


def generate_insight_for_partner(partner_id: str, metric: str = "revenue") -> dict:
    """
    Full pipeline for single partner refresh.
    Runs detection + LLM pipeline.
    Used by POST /insights/{partner_id}/refresh
    """
    partner_df = get_partner_data(partner_id, metric)
    metrics    = run_detectors(partner_df)
    return run_llm_pipeline(partner_id, metrics)