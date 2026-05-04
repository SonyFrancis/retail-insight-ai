import json
from datetime import datetime
from app.db.models import get_connection

def upsert_insight(record: dict):
    """Insert or update insight record for a partner."""
    conn = get_connection()
    conn.execute("""
        INSERT INTO insight_records (
            partner_id, trend_insights, anomaly_insights,
            contribution_insights, confidence,
            factuality_score, factuality_verdict,
            llm_faithfulness, llm_relevancy,
            claim_results, data_window, generated_at
        ) VALUES (
            :partner_id, :trend_insights, :anomaly_insights,
            :contribution_insights, :confidence,
            :factuality_score, :factuality_verdict,
            :llm_faithfulness, :llm_relevancy,
            :claim_results, :data_window, :generated_at
        )
        ON CONFLICT(partner_id) DO UPDATE SET
            trend_insights        = excluded.trend_insights,
            anomaly_insights      = excluded.anomaly_insights,
            contribution_insights = excluded.contribution_insights,
            confidence            = excluded.confidence,
            factuality_score      = excluded.factuality_score,
            factuality_verdict    = excluded.factuality_verdict,
            llm_faithfulness      = excluded.llm_faithfulness,
            llm_relevancy         = excluded.llm_relevancy,
            claim_results         = excluded.claim_results,
            data_window           = excluded.data_window,
            generated_at          = excluded.generated_at
    """, record)
    conn.commit()
    conn.close()

def get_insight(partner_id: str) -> dict | None:
    """Fetch stored insight for a partner."""
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM insight_records WHERE partner_id = ?",
        (partner_id,)
    ).fetchone()
    conn.close()
    if row is None:
        return None
    result = dict(row)
    # Deserialise claim_results from JSON string
    if result.get("claim_results"):
        result["claim_results"] = json.loads(result["claim_results"])
    return result

def list_partners() -> list[str]:
    """Return all partner IDs that have stored insights."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT partner_id FROM insight_records ORDER BY partner_id"
    ).fetchall()
    conn.close()
    return [r["partner_id"] for r in rows]