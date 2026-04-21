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
- Built using graph-based orchestration for modular, inspectable AI pipelines

## System Architecture

The pipeline follows a hybrid analytics + LLM architecture:

Retail Sales Data (CSV)
│
▼
Deterministic Analytics Layer
(Trend Detection, Anomaly Detection, Contribution Analysis)
│
▼
Structured Metrics
│
▼
Data Formatting Layer
(Popping internal fields, converting week formats to natural language)
│
▼
LangGraph Orchestration
│
├── Analyst Node (LLM Insight Generation)
├── Critic Node  (Structure Validation + Retry Logic)
└── Eval Node    (Factuality + LLM-as-Judge Evaluation)
│
▼
Structured Business Insights + Factuality Report

This architecture ensures that statistical signals are extracted deterministically,
the LLM is used only for interpretation and summarization, and all generated 
insights are verified before being surfaced to the user.

## Project Structure

retail-insight-ai/
│
├── app/
│   ├── insights/
│   │   └── detectors.py          # Trend, anomaly, contribution detectors
│   │
│   ├── graph/
│   │   ├── builder.py            # LangGraph pipeline assembly
│   │   ├── nodes.py              # Analyst, critic, eval node definitions
│   │   └── state.py              # InsightState TypedDict
│   │
│   ├── evals/
│   │   ├── init.py
│   │   ├── factuality.py         # Deterministic factuality checks
│   │   ├── llm_evals.py          # LLM-as-judge via deepeval
│   │   └── report.py             # FactualityReport dataclass
│   │
│   ├── data/
│   │   └── raw/
│   │
│   └── utils/
│
├── scripts/
│   ├── generate_synthetic.py
│   └── run_graph.py
│
├── notebooks/
│   └── EDA.ipynb
│
├── tests/
│   └── evals/
│       └── test_factuality.py    # Golden set tests for factuality eval
│
├── conftest.py
├── requirements.txt
└── README.md

## How the Pipeline Works

### 1. Data Ingestion
Retail sales data is loaded from CSV files containing date, category, 
and revenue columns.

### 2. Deterministic Signal Detection
Statistical detectors extract signals from the raw data:
- Trend detection using linear regression (slope, p-value, pct_change)
- Anomaly detection using z-score based analysis
- Contribution analysis identifying which categories drove recent revenue change

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

### 5. Critic Node — Structure Validation
The critic node validates the generated insight to ensure:
- All required JSON keys are present
- Stated percentages are traceable to source signals
- If validation fails, the insight is rejected and regenerated (max 2 retries)

### 6. Eval Node — Two-Layer Quality Evaluation

#### Layer 1 — Deterministic factuality checks (custom)
Verifies every claim in the insight against the source signals:

| Check | What it verifies |
|---|---|
| Numeric | Every percentage is within 5% relative tolerance of source data |
| Direction | Up/down language matches actual signal direction, per entity |
| Entity | Named categories exist in the dataset (fuzzy matched) |
| Currency | No currency symbols or units are present |
| Temporal | Year references exist in actual time windows |

#### Layer 2 — LLM-as-judge (deepeval + llama3)
A separate LLM (llama3 via Ollama) evaluates the insight for:
- Faithfulness — are all claims supported by the input signals?
- Relevancy — does the insight address the metrics it was given?

If the factuality verdict is `fail`, the insight is rejected and the analyst 
node is retried with explicit failure context injected into the prompt.

### 7. Confidence Scoring
Confidence is computed deterministically from the factuality eval score — 
not from LLM self-assessment:

| Factuality score | Confidence |
|---|---|
| ≥ 90% | high |
| ≥ 75% | medium |
| < 75% | low |

## Running the Project

Run the pipeline from the project root:

```bash
python -m scripts.run_graph
```

Run the factuality eval test suite:

```bash
python -m pytest tests/evals/ -v
```

## Example Output
--- FACTUALITY EVAL ---
[PASS] Factuality 100% (16/16 claims passed)
--- LLM EVAL ---
Faithfulness : 0.89
Relevancy    : 1.00
===== AI GENERATED INSIGHTS =====
Trend Insights:
Revenue for Electronics category has seen a notable increase of 14.31% from
early February 2024 to late January 2026. Fashion category has experienced
a decrease of 10.59% over the same period.
Anomaly Insights:
There have been unusual spikes and drops in Electronics revenue during
late September 2024 and November 2025. Fashion experienced unexpected
increases in April 2024. Home showed a sudden increase in May 2025.
Contribution Insights:
During the week of January 19-25, 2026, Electronics contributed 48.15%
to overall revenue growth, followed by Home at 34.84%, Fashion at 14.77%,
and Grocery at 2.24%.
Confidence: high

## Technologies Used

- Python
- Pandas / NumPy / SciPy
- LangGraph
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
- Confidence scoring reflects LLM faithfulness, not underlying data 
  signal strength. P-values and z-scores are available in raw metrics 
  for signal quality assessment.

## Future Improvements

- FastAPI serving layer with async endpoints and SSE streaming
- Multi-KPI expansion (margin, inventory, basket size)
- RAG memory for historical insight retrieval
- Cross-KPI correlation analysis
- Observability and eval score drift tracking
- CI/CD pipeline with eval gate

## Motivation

Retail organizations generate vast amounts of transactional data, but analysts 
often spend significant time manually interpreting metrics. This project 
demonstrates how AI systems can bridge the gap between raw data and 
decision-making insights by combining traditional analytics with 
LLM-driven interpretation.

## Author

Sony Francis  
Machine Learning Engineer | Applied AI Systems