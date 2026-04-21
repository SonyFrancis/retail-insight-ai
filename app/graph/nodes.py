import ollama
import json
import re

from app.evals.factuality import run_factuality_eval
from app.evals.llm_evals import run_llm_evals
from app.insights.detectors import format_metrics_for_llm  # ← add import


def analyst_node(state):
    metrics = state["metrics"]

    # Pre-format time references before passing to LLM
    formatted_metrics = format_metrics_for_llm(metrics)   

    # ADD: Build failure feedback from previous eval if present
    eval_feedback = ""
    report = state.get("factuality_report")
    if report and report.verdict == "fail":
        failed = [r for r in report.results if not r.passed]
        failure_lines = "\n".join(
            f"- {r.check_type}: '{r.claim_text}' — {r.note}"
            for r in failed
        )
        eval_feedback = f"""Previous insight was rejected for these factuality failures:
                    {failure_lines}

                    Correct these specifically before generating the new insight.
                    """

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
            - Do NOT repeat raw JSON data
            - Highlight the most important patterns
            - Only state percentages that appear explicitly in the metrics
            - Do NOT combine or sum contribution percentages — report each category separately
            - You MUST NOT use any currency symbols or currency words anywhere in the output
            - Time periods are already provided in natural language — use them exactly as given, do not reformat or invent dates
            - Do NOT invent numbers or introduce new metrics
            - Keep each insight concise (1-2 sentences)
            - If no trend is detected, say "No significant trend detected."
            - If no anomalies are detected, say "No significant anomalies detected."
            - If contribution analysis is not meaningful, say "No major contribution changes detected."
            - Output valid JSON only.
            """


    response = ollama.chat(
        model="mistral",  # or llama3 if installed
        messages=[{"role": "user", "content": prompt}],
    )

    content = response["message"]["content"]

    # print("\n--- ANALYST NODE ---")
    # print("LLM raw response:")
    # print(content)

    try:
        parsed = json.loads(content)

        required_keys = [
            "trend_insights",
            "anomaly_insights",
            "contribution_insights"
        ]

        if all(k in parsed for k in required_keys):
            state["insight"] = parsed
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
    print(f"\n--- LLM EVAL ---")
    print(f"Faithfulness : {llm_eval_result['faithfulness_score']:.2f} — {llm_eval_result['faithfulness_reason']}")
    print(f"Relevancy    : {llm_eval_result['relevancy_score']:.2f} — {llm_eval_result['relevancy_reason']}")

    if verbose:
        for r in report.results:
            status = "PASS" if r.passed else "FAIL"
            print(f"  [{status}] {r.check_type:10s} | {r.claim_text:30s} | {r.note}")

    return state