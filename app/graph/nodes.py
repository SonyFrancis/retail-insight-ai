import re
import os
import json
from groq import Groq

from app.evals.factuality import run_factuality_eval
from app.evals.llm_evals import run_llm_evals
from app.insights.detectors import format_metrics_for_llm  

# Initialise Groq client
client = Groq(api_key=os.environ.get("GROQ_API_KEY"))


# ── Post-processing guardrail ───────────────────────────────────────── #
_CURRENCY_SYMBOLS = ["$", "£", "€", "¥", "₹"]
_CURRENCY_WORDS   = ["dollars", "USD", "GBP", "EUR", "rupees"]

def clean_insight(insight: dict) -> dict:
    import copy
    cleaned = copy.deepcopy(insight)

    for field in ["trend_insights", "anomaly_insights", "contribution_insights"]:
        text = cleaned.get(field, "")
        
        # Guard — ensure it's a string before processing
        if not isinstance(text, str):
            cleaned[field] = str(text)
            continue
            
        for sym in _CURRENCY_SYMBOLS:
            text = text.replace(sym, "")
        for word in _CURRENCY_WORDS:
            text = re.sub(rf'\b{word}\b', '', text, flags=re.IGNORECASE)
        text = re.sub(r'  +', ' ', text).strip()
        cleaned[field] = text

    return cleaned


def analyst_node(state):
    # Reset eval results on each attempt
    state["factuality_report"] = None
    state["llm_eval_result"]   = None
    metrics = state["metrics"]

    eval_feedback = ""
    report = state.get("factuality_report")
    if report and report.verdict == "fail":
        failed = [r for r in report.results if not r.passed]
        failure_lines = "\n".join(
            f"- {r.check_type}: '{r.claim_text}' — {r.note}"
            for r in failed
        )
        eval_feedback = f"""
                    Previous insight was rejected for these factuality failures:
                    {failure_lines}

                    Correct these specifically before generating the new insight.
                    """

    formatted_metrics = format_metrics_for_llm(metrics)

    prompt = f"""
            You are a retail analytics assistant.

            You are given deterministic analytics results from a data pipeline.

            Metrics:
            {formatted_metrics}

            {eval_feedback}

            Generate structured business insights in JSON format:

            {{
            "trend_insights": "...",
            "anomaly_insights": "...",
            "contribution_insights": "..."
            }}

            Instructions:
            - Summarize the metrics in natural language for a non-technical business audience
            - ALL three fields must be plain strings — never return a dict or object
            - Do NOT repeat raw JSON data
            - Highlight the most important patterns
            - Only state percentages that appear explicitly in the metrics
            - Do NOT combine or sum contribution percentages — report each category separately
            - You MUST NOT use any currency symbols or currency words anywhere in the output
            - Time periods are already provided in natural language — use them exactly as given
            - Do NOT invent numbers or introduce new metrics
            - Keep each insight concise (1-2 sentences)
            - If no trend is detected, say "No significant trend detected."
            - If no anomalies are detected, say "No significant anomalies detected."
            - If contribution analysis is not meaningful, say "No major contribution changes detected."
            - Output valid JSON only
            """

    # ── Groq replaces Ollama ──────────────────────────────────────────
    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",      # fast, free tier
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,             # low temperature for factual output
        response_format={"type": "json_object"},  # enforces JSON output
    )

    content = response.choices[0].message.content
    # ─────────────────────────────────────────────────────────────────

    # Groq sometimes wraps in markdown code fences — strip them
    content = re.sub(r'^```json\s*', '', content.strip())
    content = re.sub(r'\s*```$', '', content.strip())

    try:
        # content is always a string — parse it
        if isinstance(content, str):
            parsed = json.loads(content)
        else:
            parsed = content  # already dict in rare cases

        required_keys = [
            "trend_insights",
            "anomaly_insights",
            "contribution_insights",
        ]

        # Flatten any dict values to strings
        for key in required_keys:
            val = parsed.get(key, "")
            if isinstance(val, dict):
                parsed[key] = " ".join(str(v) for v in val.values())
            elif not isinstance(val, str):
                parsed[key] = str(val)

        if all(k in parsed for k in required_keys):
            state["insight"] = clean_insight(parsed)
        else:
            print("Missing keys in response")
            state["insight"] = None

    except Exception as e:
        print("JSON parsing failed:", e)
        state["insight"] = None

    return state


def critic_node(state):
    MAX_RETRIES = 2

    if state["retry_count"] >= MAX_RETRIES:
        state["approved"] = True
        return state

    insight = state.get("insight")
    metrics = state.get("metrics")

    if not insight:
        state["approved"] = False
        state["retry_count"] += 1
        return state

    # Validate trend percentages
    trend_text = insight.get("trend_insights", "")

    percentages = re.findall(r"-?\d+\.?\d*%", trend_text)

    expected_percents = [
        f"{t['pct_change']}%"
        for t in metrics.get("trend_results", [])
    ]

    if percentages and not any(p in expected_percents for p in percentages):
        state["approved"] = False
        state["retry_count"] += 1
        print("Critic rejected insight. Retrying...")
    else:
        state["approved"] = True

    return state

def eval_node(state, verbose: bool = True):
    """
    Runs factuality eval on the approved insight.
    Runs AFTER critic approves — never during retry loop.
    """
    insight = state.get("insight")
    metrics = state.get("metrics")

    if not insight or not metrics:
        state["factuality_report"] = None
        return state

    report = run_factuality_eval(insight, metrics)
    llm_eval_result = run_llm_evals(insight, metrics)

    state["factuality_report"] = report
    state["llm_eval_result"]   = llm_eval_result

    # Print to console so it shows alongside existing output
    print(f"\n--- FACTUALITY EVAL ---")
    print(report.summary())

    if verbose:
        print(f"\n--- LLM EVAL ---")
        if llm_eval_result and llm_eval_result.get("faithfulness_score") is not None:
            print(f"Faithfulness : {llm_eval_result['faithfulness_score']:.2f} — {llm_eval_result['faithfulness_reason']}")
            print(f"Relevancy    : {llm_eval_result['relevancy_score']:.2f} — {llm_eval_result['relevancy_reason']}")
        else:
            print("LLM eval skipped — judge model returned invalid output")
    return state