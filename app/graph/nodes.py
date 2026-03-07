import ollama
import json
import re


def analyst_node(state):
    metrics = state["metrics"]
    prompt = f"""
            You are a retail analytics assistant.

            You are given deterministic analytics results from a data pipeline.

            Metrics:
            {metrics}

            Generate structured business insights in JSON format:

            {{
            "trend_insights": "...",
            "anomaly_insights": "...",
            "contribution_insights": "...",
            "confidence": "low | medium | high"
            }}

            Instructions:
            - Summarize the metrics in natural language
            - Do NOT repeat raw JSON data
            - Highlight the most important patterns
            - Mention percentages or slopes only when relevant
            - Keep each insight concise (1-2 sentences)
            - If no trend is detected, say "No significant trend detected."
            - If no anomalies are detected, say "No significant anomalies detected."
            - If contribution analysis is not meaningful, say "No major contribution changes detected."
            - Output valid JSON only
            """

    # prompt = f"""
    #             You are a retail analytics assistant.

    #             You are given statistical trend detection results from deterministic analysis.

    #             Metrics:
    #             {metrics}

    #             Generate a concise business insight in JSON format:

    #             {{
    #             "summary": "...",
    #             "confidence": "low | medium | high"
    #             }}

    #             Rules:
    #             - Only describe the detected trends
    #             - Do NOT invent numbers
    #             - Do NOT introduce new metrics
    #             - Do not infer or invent currency symbols.
    #             - If a unit is not provided, refer to values without a currency symbol.
    #             - Output valid JSON only
    #             """

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
            "contribution_insights",
            "confidence"
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