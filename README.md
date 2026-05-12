# Retail Insight AI

[![Live API](https://img.shields.io/badge/Live%20API-GCP%20Cloud%20Run-blue)](https://retail-insight-ai-250509873578.us-central1.run.app/docs)
[![Docker](https://img.shields.io/badge/Docker-Containerised-blue)](https://www.docker.com)

> **Live Swagger UI:** https://retail-insight-ai-250509873578.us-central1.run.app/docs

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
- Uses hosted LLMs (Groq) to generate human-readable business insights
- Validates insights deterministically against source signals
- Evaluates LLM output quality using a two-layer eval architecture
- Serves insights via a REST API deployed on GCP Cloud Run
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
                        ├── Analyst Node  (Groq LLM Insight Generation)
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
                        │
                        ▼
            GCP Cloud Run (Docker container, public URL)
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
│   │   ├── llm_evals.py              # LLM-as-judge via deepeval + Groq
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
├── Dockerfile                        # Multi-stage Docker build
├── docker-compose.yml                # Local development setup
├── .dockerignore
├── .env.example                      # Environment variable template
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
A hosted LLM (llama3 via Groq API) generates structured business insights in JSON
format covering trend, anomaly, and contribution observations. The prompt enforces:

- Non-technical business language
- No currency symbols or invented metrics
- Per-category contribution reporting without aggregation
- JSON output mode enforced at the API level for reliable structured output

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
| Temporal | Year references exist in actual time windows across all signal types |

#### Layer 2 — LLM-as-judge (deepeval + Groq)
A separate LLM (llama3-3.3-70b via Groq API) evaluates the insight for:

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

### 10. Cloud Deployment
The application is containerised using a multi-stage Docker build and deployed
on GCP Cloud Run:

- **Multi-stage Dockerfile** — builder stage installs dependencies, runtime stage
  copies only what's needed, keeping the image lean and secure
- **Non-root user** — container runs as a non-root user for security
- **GCP Artifact Registry** — Docker image stored and versioned in GCP
- **GCP Cloud Run** — serverless container execution with automatic scaling,
  scales to zero when not in use (zero cost at rest)
- **Environment variables** — API keys injected at runtime via Cloud Run
  environment config, never baked into the image

## Running the Project Locally

**Prerequisites:**

```bash
cp .env.example .env   # add your API keys to .env
```

Required environment variables:

```
GROQ_API_KEY=your_groq_api_key
LANGSMITH_API_KEY=your_langsmith_api_key
LANGSMITH_TRACING=true
LANGSMITH_PROJECT=retail-insight-ai
```

**Option 1 — Docker (recommended):**

```bash
docker-compose up
```

**Option 2 — Local venv:**

```bash
pip install -r requirements.txt
uvicorn app.api.main:app --reload
```

Pre-compute insights for all partners:

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

Access the local Swagger UI at:

```
http://localhost:8080/docs
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
  "trend_insights": "Revenue for Electronics has seen a notable increase of 15.78% from week of Apr 29, 2024 to week of Apr 20, 2026.",
  "anomaly_insights": "Unusual revenue drops were observed in Electronics during Sep 2024 and spikes during Apr 2026. Fashion showed unexpected increases in Apr 2025.",
  "contribution_insights": "During the week of Apr 20, 2026, Electronics contributed 51.96% to overall revenue growth, followed by Home at 38.1%, Fashion at 8.38%, and Grocery at -1.56%.",
  "confidence": "high",
  "generated_at": "2026-05-12T02:00:00Z",
  "data_window": "May 2024 – Apr 2026"
}
```

`GET /insights/PARTNER_001/debug` additionally returns:

```json
{
  "factuality_score": 1.0,
  "factuality_verdict": "pass",
  "llm_faithfulness": 0.86,
  "llm_relevancy": 1.0,
  "claim_results": [
    {"claim_text": "15.78%", "check_type": "numeric", "passed": true, "note": "closest=15.78, relative_delta=0.0%"},
    {"claim_text": "Electronics", "check_type": "entity", "passed": true, "note": "fuzzy match: electronics"}
  ]
}
```

## Technologies Used

- Python 3.11
- Pandas / NumPy / SciPy
- LangGraph
- FastAPI + Uvicorn
- SQLite
- Docker + GCP Cloud Run + GCP Artifact Registry
- Groq API (hosted LLM inference — llama3 for generation, llama3-3.3-70b for evaluation)
- deepeval (LLM evaluation framework)
- pytest (golden set testing)
- python-dotenv (environment management)

## Known Limitations

- LLM-as-judge faithfulness scores may be lower than expected due to
  format-level mismatches between raw date formats in retrieval context
  and natural language dates in generated insights. Deterministic checks
  confirm factual accuracy independently.
- SQLite DB is baked into the Docker image at build time — insights persist
  across requests within a container instance but reset on new deployments.
  Production fix: persist DB to GCP Cloud Storage or migrate to Cloud SQL.
- Groq free tier has token-per-minute rate limits — a sleep buffer is applied
  between generation and judge calls to avoid rate limit errors.
- Confidence scoring reflects LLM faithfulness, not underlying data
  signal strength. P-values and z-scores are available in raw metrics
  for signal quality assessment.

## Future Improvements

- Persistent storage via GCP Cloud Storage or Cloud SQL
- Multi-KPI expansion (margin, inventory, basket size)
- RAG memory for historical insight retrieval
- Cross-KPI correlation analysis
- Observability and eval score drift tracking (LangSmith)
- CI/CD pipeline with eval gate (GitHub Actions)
- Scheduled nightly precompute (Cloud Scheduler + Cloud Run Jobs)

## Motivation

Retail organizations generate vast amounts of transactional data, but analysts
often spend significant time manually interpreting metrics. This project
demonstrates how AI systems can bridge the gap between raw data and
decision-making insights by combining traditional analytics with
LLM-driven interpretation.

## Author

Sony Francis
Machine Learning Engineer | Applied AI Systems
