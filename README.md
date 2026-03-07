# Retail Insight AI

Retail Insight AI is an AI-powered analytics pipeline that automatically generates business insights from retail sales data.

The system combines deterministic statistical analysis with LLM-based summarization to produce structured insights such as:

- Revenue trends
- Anomalous sales events
- Category contribution analysis

The goal is to simulate how modern AI systems can assist analysts by converting raw metrics into interpretable business insights.

## Key Features

- Detects statistically significant trends using linear regression
- Identifies anomalous revenue spikes and drops
- Computes category contribution to revenue change
- Uses LLMs to generate human-readable insights
- Implements a validation layer to guard against hallucinated metrics
- Built using graph-based orchestration for modular AI pipelines

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
LangGraph Orchestration
        │
        ├── Analyst Node (LLM Insight Generation)
        └── Critic Node (Validation + Retry Logic)
        │
        ▼
Structured Business Insights

This architecture ensures that statistical signals are extracted deterministically, while the LLM is used only for interpretation and summarization.

## Project Structure

retail-insight-ai
│
├── app
│   ├── insights
│   │   └── detectors.py
│   │   
│   ├── graph
│   │   ├── builder.py
│   │   └── nodes.py
│   │
│   ├── data
│   │   └── raw
│   │
│   └── utils
│
├── scripts
│   ├── generate_synthetic.py
│   └── run_graph.py
│
├── notebooks
│   └── EDA.ipynb
│
├── tests
│
├── requirements.txt
└── README.md

### How the Pipeline Works
1. Data Ingestion
Retail sales data is loaded from CSV files.

2. Deterministic Signal Detection
Statistical detectors extract signals such as:
Trend detection using linear regression
Anomaly detection using z-score based analysis
Contribution analysis identifying category drivers

3. Structured Metrics Generation
All signals are converted into structured metrics that serve as input to the LLM.

4. Insight Generation
An LLM generates natural language insights summarizing the signals.

5. Validation Layer
A critic node validates the insight to ensure:
Required structure exists
No hallucinated numerical values appear
If validation fails, the system retries insight generation.

### Running the Project
Run the pipeline from the project root:
python -m scripts.run_graph

Example Output
===== AI GENERATED INSIGHTS =====

Trend Insights:
Electronics revenue increased by 14.31% with a strong upward slope, while Fashion revenue declined by 10.59%.

Anomaly Insights:
Multiple anomalies were observed in Electronics during September 2024 and November 2025.

Contribution Insights:
Electronics contributed nearly half of the most recent revenue growth (48.15%), followed by Home.

Confidence: medium

===============================

## Technologies Used
- Python
- Pandas / NumPy
- SciPy
- LangGraph
- Ollama (local LLM inference)
- Mistral / Llama models

## Future Improvements
- LLM evaluation frameworks for insight quality
- Serving insights through FastAPI endpoints
- Multi-agent orchestration for deeper reasoning
- Integration with vector databases for contextual retrieval
- Automated insight dashboards

## Motivation
Retail organizations generate vast amounts of transactional data, but analysts often spend significant time manually interpreting metrics.

This project demonstrates how AI systems can bridge the gap between raw data and decision-making insights by combining traditional analytics with LLM-driven interpretation.

### Author
Sony Francis
Machine Learning Engineer | Applied AI Systems