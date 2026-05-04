# Retail Insight AI

Retail Insight AI is an AI-powered analytics pipeline that automatically generates
business insights from retail sales data.

The system combines deterministic statistical analysis with LLM-based summarization
to produce structured insights such as:

- Revenue trends
- Anomalous sales events
- Category contribution analysis

The goal is to simulate how modern AI systems can assist analysts by converting
raw metrics into interpretable business insights.

## Key Features

- Detects statistically significant trends using linear regression
- Identifies anomalous revenue spikes and drops using z-score analysis
- Computes category contribution to revenue change
- Uses LLMs to generate human-readable business insights
- Validates insights deterministically against source signals
- Evaluates LLM output quality using a two-layer eval architecture
- Serves insights via a REST API with partner-level access control
- Supports batch pre-computation and on-demand refresh per partner
- Built using graph-based orchestration for modular, inspectable AI pipelines

## System Architecture

The pipeline follows a hybrid analytics + LLM architecture:

```
Retail Sales Data (CSV)
        │
        ▼
Partner Data Layer
(Filter by partner_id, aggregate across stores)
        │
        ├── Batch path (precompute)        Single partner path (refresh)
        │   run_detectors_batch()      │   run_detectors()
        │   all partners, one pass     │   one partner only
        │                              │
        └──────────────────────────────┘
                        │
                        ▼
            Data Formatting Layer
  (Remove internal fields, convert week formats to natural language)
                        │
                        ▼
            LangGraph Orchestration
                        │
                        ├── Analyst Node  (LLM Insight Generation)
                        ├── Critic Node   (Structure Validation + Retry Logic)
                        └── Eval Node     (Factuality + LLM-as-Judge Evaluation)
                        │
                        ▼
            Structured Business Insights + Factuality Report
                        │
                        ▼
                SQLite Insight Store
                        │
                        ▼
                FastAPI REST Layer
                        │
                        ├── GET  /insights/{partner_id}         (account executives)
                        ├── GET  /insights/{partner_id}/debug   (operators)
                        ├── POST /insights/{partner_id}/refresh (on-demand generation)
                        └── GET  /insights/                     (list all partners)
```

This architecture ensures that statistical signals are extracted deterministically,
the LLM is used only for interpretation and summarization, all generated insights
are verified before being stored, and business users get instant responses from
pre-computed results.

## Project Structure

```
retail-insight-ai/
│
├── app/
│   ├── api/
│   │   ├── main.py                   # FastAPI app entry point
│   │   ├── routes/
│   │   │   └── insights.py           # Endpoint definitions
│   │   ├── schemas/
│   │   │   └── insight.py            # Pydantic request/response models
│   │   └── services/
│   │       ├── data.py               # Partner data loading + caching
│   │       └── insight_service.py    # Pipeline orchestration
│   │
│   ├── db/
│   │   ├── models.py                 # SQLite table definitions + init
│   │   └── crud.py                   # Read/write operations
│   │
│   ├── insights/
│   │   └── detectors.py              # Trend, anomaly, contribution detectors
│   │                                 # includes run_detectors_batch()
│   │
│   ├── graph/
│   │   ├── builder.py                # LangGraph pipeline assembly
│   │   ├── nodes.py                  # Analyst, critic, eval node definitions
│   │   └── state.py                  # InsightState TypedDict
│   │
│   ├── evals/
│   │   ├── __init__.py
│   │   ├── factuality.py             # Deterministic factuality checks
│   │   ├── llm_evals.py              # LLM-as-judge via deepeval
│   │   └── report.py                 # FactualityReport dataclass
│   │
│   ├── data/
│   │   ├── raw/
│   │   │   └── sales.csv             # Synthetic retail sales data
│   │   └── insights.db               # SQLite store for pre-computed insights
│   │
│   └── utils/
│
├── scripts/
│   ├── generate_synthetic.py         # Synthetic data generation
│   ├── precompute_insights.py        # Batch insight pre-computation
│   └── run_graph.py                  # CLI pipeline runner
│
├── notebooks/
│   └── EDA.ipynb
│
├── tests/
│   └── evals/
│       └── test_factuality.py        # Golden set tests for factuality eval
│
├── conftest.py
├── requirements.txt
└── README.md
```

## How the Pipeline Works

### 1. Data Ingestion
Retail sales data is loaded from a CSV file containing date, partner_id, store_id,
region, category, and revenue columns. Each partner owns multiple stores — insights
are generated at the partner level, aggregated across all their stores.

### 2. Detection — Batch vs Single Partner

**Batch path (nightly precompute):**
`run_detectors_batch()` processes all partners in a single grouped pass — three
groupby operations regardless of partner count. This is significantly faster than
calling `run_detectors()` per partner sequentially.

**Single partner path (on-demand refresh):**
`run_detectors()` filters data for one partner and runs detection. Used by the
`/refresh` API endpoint.

Both paths produce the same structured metrics dict expected by the LangGraph pipeline.

### 3. Data Formatting
Before reaching the LLM, metrics are pre-processed to ensure business-readability:

- Internal statistical fields (weekly_slope, z_score, p_value, raw value) are removed
- ISO week formats are converted to natural language (e.g. "week of Sep 09, 2024")
- Only business-relevant fields (pct_change, direction, entity, contribution_pct)
  are passed to the prompt

### 4. Analyst Node — LLM Insight Generation
A local LLM (Mistral via Ollama) generates structured business insights in JSON format
covering trend, anomaly, and contribution observations. The prompt enforces:

- Non-technical business language
- No currency symbols or invented metrics
- Per-category contribution reporting without aggregation

A post-generation `clean_insight()` pass deterministically strips any currency
symbols that slip through prompt instructions.

### 5. Critic Node — Structure Validation
The critic node validates the generated insight to ensure:

- All required JSON keys are present
- Stated percentages are traceable to source signals
- If validation fails, the insight is rejected and regenerated (max 2 retries)

### 6. Eval Node — Two-Layer Quality Evaluation

#### Layer 1 — Deterministic factuality checks (custom)

| Check | What it verifies |
|---|---|
| Numeric | Every percentage is within 5% relative tolerance of source data |
| Direction | Up/down language matches actual signal direction, per entity |
| Entity | Named categories exist in the dataset (fuzzy matched) |
| Currency | No currency symbols or units are present |
| Temporal | Year references exist in actual time windows |

#### Layer 2 — LLM-as-judge (deepeval + llama3)
A separate LLM (llama3 via Ollama) evaluates the insight for:

- **Faithfulness** — are all claims supported by the input signals?
- **Relevancy** — does the insight address the metrics it was given?

If the factuality verdict is `fail`, the insight is rejected and the analyst
node is retried with explicit failure context injected into the prompt.
If the judge model fails to return valid JSON, the eval is skipped gracefully
and the pipeline continues.

### 7. Confidence Scoring
Confidence is computed deterministically from the factuality eval score —
not from LLM self-assessment:

| Factuality score | Confidence |
|---|---|
| ≥ 90% | high |
| ≥ 75% | medium |
| < 75% | low |

### 8. Storage
Verified insights are stored in SQLite with full eval metadata:

| Field | Description |
|---|---|
| partner_id | Primary key |
| trend/anomaly/contribution_insights | Generated insight text |
| confidence | Deterministic confidence label |
| factuality_score | Overall factuality score (0–1) |
| factuality_verdict | pass / warn / fail |
| llm_faithfulness | deepeval faithfulness score |
| llm_relevancy | deepeval relevancy score |
| claim_results | Per-claim JSON breakdown |
| data_window | Human-readable date range |
| generated_at | UTC timestamp |

### 9. FastAPI Serving Layer
Insights are served via a REST API with two response levels:

**Business users** — `GET /insights/{partner_id}`
Returns clean insight text and confidence score. No eval detail.

**Operators** — `GET /insights/{partner_id}/debug`
Returns full eval breakdown including factuality score, verdict,
LLM eval scores, and per-claim results.

**On-demand refresh** — `POST /insights/{partner_id}/refresh`
Triggers fresh insight generation for a single partner. Runs the
full pipeline and updates the DB record.

## Running the Project

Start the API server:

```bash
uvicorn app.api.main:app --reload
```

Pre-compute insights for all partners (batch):

```bash
python -m scripts.precompute_insights
```

Run the CLI pipeline directly:

```bash
python -m scripts.run_graph
```

Run the factuality eval test suite:

```bash
python -m pytest tests/evals/ -v
```

Access the auto-generated Swagger UI at:

```
http://localhost:8000/docs
```

## API Endpoints

| Method | Endpoint | Description | Audience |
|---|---|---|---|
| GET | `/insights/{partner_id}` | Latest stored insight | Account executives |
| GET | `/insights/{partner_id}/debug` | Full eval detail | Operators |
| POST | `/insights/{partner_id}/refresh` | Trigger fresh generation | Internal |
| GET | `/insights/` | List all partners with stored insights | Internal |
| GET | `/health` | Health check | Internal |

## Example API Response

`GET /insights/PARTNER_001`:

```json
{
  "partner_id": "PARTNER_001",
  "trend_insights": "Revenue for Electronics has seen a notable increase of 14.31% from early February 2024 to late January 2026. Fashion has experienced a decrease of 10.59% over the same period.",
  "anomaly_insights": "Unusual spikes were observed in Electronics during late September 2024 and November 2025. Fashion showed unexpected increases in April 2024.",
  "contribution_insights": "During the week of January 19-25 2026, Electronics contributed 48.15% to overall revenue growth, followed by Home at 34.84%, Fashion at 14.77%, and Grocery at 2.24%.",
  "confidence": "high",
  "generated_at": "2026-04-26T02:00:00Z",
  "data_window": "May 2024 – Apr 2026"
}
```

`GET /insights/PARTNER_001/debug` additionally returns:

```json
{
  "factuality_score": 1.0,
  "factuality_verdict": "pass",
  "llm_faithfulness": 0.89,
  "llm_relevancy": 1.0,
  "claim_results": [
    {"claim_text": "14.31%", "check_type": "numeric", "passed": true, "note": "closest=14.31, relative_delta=0.0%"},
    {"claim_text": "Electronics", "check_type": "entity", "passed": true, "note": "fuzzy match: electronics"}
  ]
}
```

## Technologies Used

- Python
- Pandas / NumPy / SciPy
- LangGraph
- FastAPI + Uvicorn
- SQLite
- Ollama (local LLM inference)
- Mistral (insight generation)
- Llama3 (LLM-as-judge evaluation)
- deepeval (LLM evaluation framework)
- pytest (golden set testing)

## Known Limitations

- LLM-as-judge faithfulness scores may be lower than expected due to
  format-level mismatches between ISO week dates in retrieval context
  and natural language dates in generated insights. Deterministic checks
  confirm factual accuracy independently.
- Same LLM family (Mistral) used for both generation and criticism in the
  critic node — an independent model is recommended for production.
- Local Ollama inference is single-threaded — LLM generation is sequential
  regardless of batch size. Increasing MAX_LLM_WORKERS requires a hosted
  LLM API (GPT-4, Claude) that supports concurrent requests.
- Confidence scoring reflects LLM faithfulness, not underlying data
  signal strength. P-values and z-scores are available in raw metrics
  for signal quality assessment.

## Future Improvements

- Multi-KPI expansion (margin, inventory, basket size)
- RAG memory for historical insight retrieval
- Cross-KPI correlation analysis
- Observability and eval score drift tracking (LangSmith / Arize)
- CI/CD pipeline with eval gate (GitHub Actions)
- Scheduled nightly precompute (APScheduler / Celery)

## Motivation

Retail organizations generate vast amounts of transactional data, but analysts
often spend significant time manually interpreting metrics. This project
demonstrates how AI systems can bridge the gap between raw data and
decision-making insights by combining traditional analytics with
LLM-driven interpretation.

## Author

Sony Francis
Machine Learning Engineer | Applied AI Systems
