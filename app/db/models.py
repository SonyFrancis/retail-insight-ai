import sqlite3
import json
from pathlib import Path

DB_PATH = Path("app/data/insights.db")

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Create tables if they don't exist."""
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS insight_records (
            partner_id          TEXT PRIMARY KEY,
            trend_insights      TEXT NOT NULL,
            anomaly_insights    TEXT NOT NULL,
            contribution_insights TEXT NOT NULL,
            confidence          TEXT NOT NULL,
            factuality_score    REAL,
            factuality_verdict  TEXT,
            llm_faithfulness    REAL,
            llm_relevancy       REAL,
            claim_results       TEXT,   -- JSON serialised list
            data_window         TEXT,
            generated_at        TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()
    print("✅ DB initialised")