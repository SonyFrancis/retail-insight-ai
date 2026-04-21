import re
from difflib import get_close_matches
from app.evals.report import ClaimResult, FactualityReport

_ENTITY_STOPWORDS = {
    "no", "not", "the", "a", "an", "with", "while", "by", "in", "of",
    "and", "or", "for", "to", "from", "during", "anomalies", "anomaly",
    "revenue", "significant", "trend", "detected", "contributed", "recent",
    "strong", "upward", "downward", "slope", "growth", "change", "week",
    "multiple", "major", "nearly", "half", "most", "there", "also",
    "around", "early", "late", "mid", "seems", "noticeable", "unusual",
    "unexpected", "approximately",
    "january", "february", "march", "april", "may", "june",
    "july", "august", "september", "october", "november", "december",
}

# ── Claim extraction ──────────────────────────────────────────────────

def _extract_percentages(text: str) -> list[float]:
    """Pull every number preceding a % sign from insight text."""
    return [float(m) for m in re.findall(r"-?\d+\.?\d*(?=%)", text)]

def _check_numeric_value(
    stated_pct: float,
    numeric_pool: list[float],
    tolerance: float,
) -> ClaimResult:
    if not numeric_pool:
        return ClaimResult(
            claim_text=f"{stated_pct}%",
            check_type="numeric",
            passed=False,
            stated_value=stated_pct,
            actual_value=None,
            note="empty numeric pool",
        )
    closest = min(numeric_pool, key=lambda x: min(
        abs(x - stated_pct),
        abs(abs(x) - abs(stated_pct))
    ))
    delta = min(
        abs(closest - stated_pct),
        abs(abs(closest) - abs(stated_pct))
    ) / (abs(closest) + 1e-9)

    return ClaimResult(
        claim_text=f"{stated_pct}%",
        check_type="numeric",
        passed=delta <= tolerance,
        stated_value=stated_pct,
        actual_value=closest,
        note=f"closest={closest:.2f}, relative_delta={delta*100:.1f}%",
    )


def _extract_direction(text: str) -> str | None:
    text_lower = text.lower()
    up_words   = ["increas", "grew", "rose", "up", "higher", "gain",
                  "climb", "spike", "spikes", "surge"]          # ← add spike/surge
    down_words = ["decreas", "fell", "drop", "down", "lower",
                  "declin", "shrink", "drops", "dip"]           # ← add drop/dip
    if any(w in text_lower for w in up_words):
        return "increase"
    if any(w in text_lower for w in down_words):
        return "decrease"
    return None


def _build_valid_entities(metrics: dict) -> set[str]:
    """Collect all entity values from every detector result."""
    entities = set()
    for result_list in [
        metrics.get("trend_results", []),
        metrics.get("anomalies_detected", []),
        metrics.get("contribution_analysis", []),
    ]:
        for item in result_list:
            for v in item.get("entity", {}).values():
                entities.add(str(v).lower())
    return entities


# ── Individual checks ─────────────────────────────────────────────────

def _check_numeric(
    stated_pct: float,
    trend_results: list[dict],
    tolerance: float = 0.05,
) -> ClaimResult:
    """
    Find the closest matching pct_change in trend_results.
    Pass if within `tolerance` relative error.
    """
    if not trend_results:
        return ClaimResult(
            claim_text=f"{stated_pct}%",
            check_type="numeric",
            passed=False,
            stated_value=stated_pct,
            actual_value=None,
            note="No trend results to verify against",
        )

    all_pcts = [t["pct_change"] for t in trend_results]
    # Find the closest actual value to what was stated
    closest = min(all_pcts, key=lambda x: abs(x - stated_pct))
    delta = abs(closest - stated_pct) / (abs(closest) + 1e-9)

    return ClaimResult(
        claim_text=f"{stated_pct}%",
        check_type="numeric",
        passed=delta <= tolerance,
        stated_value=stated_pct,
        actual_value=closest,
        note=f"closest actual={closest:.2f}%, relative_delta={delta*100:.1f}%",
    )


def _check_direction(
    stated_direction: str,
    insight_text: str,
    trend_results: list[dict],
) -> ClaimResult:
    """
    If a specific entity is mentioned in the text alongside a direction,
    verify that entity's actual direction matches. Falls back to majority
    direction if no specific entity is identifiable.
    """
    # Try to find which entity this direction claim is about
    matched_trend = None
    for trend in trend_results:
        entity_name = list(trend["entity"].values())[0]
        if entity_name.lower() in insight_text.lower():
            matched_trend = trend
            break  # use first entity match found in text

    if matched_trend:
        actual_direction = matched_trend["direction"]
        passed = stated_direction == actual_direction
        return ClaimResult(
            claim_text=f"direction={stated_direction}",
            check_type="direction",
            passed=passed,
            stated_value=stated_direction,
            actual_value=actual_direction,
            note=f"entity='{list(matched_trend['entity'].values())[0]}' "
                 f"actual={actual_direction}",
        )

    # No entity match — check if stated direction exists at all
    actual_directions = {t["direction"] for t in trend_results}
    passed = stated_direction in actual_directions
    return ClaimResult(
        claim_text=f"direction={stated_direction}",
        check_type="direction",
        passed=passed,
        stated_value=stated_direction,
        actual_value=str(actual_directions),
        note=f"no entity match; actual directions: {actual_directions}",
    )



def _check_entities(
    insight_text: str,
    valid_entities: set[str],
) -> list[ClaimResult]:
    """
    Only check tokens that look like domain entity names —
    not sentence-starting capitals or generic analytics words.
    """
    # Mid-sentence capitals only — skip the first word of each sentence
    sentences = re.split(r'(?<=[.!?])\s+', insight_text)
    candidates = set()

    for sentence in sentences:
        words = sentence.split()
        # Skip index 0 (sentence start capital), check rest
        for word in words[1:]:
            # Strip punctuation
            clean = re.sub(r'[^a-zA-Z]', '', word)
            if (
                clean
                and clean[0].isupper()
                and len(clean) > 2
                and clean.lower() not in _ENTITY_STOPWORDS
            ):
                candidates.add(clean)

    if not candidates:
        return []

    results = []
    for candidate in candidates:
        matches = get_close_matches(
            candidate.lower(), valid_entities, n=1, cutoff=0.8
        )
        results.append(ClaimResult(
            claim_text=candidate,
            check_type="entity",
            passed=bool(matches),
            stated_value=candidate,
            actual_value=matches[0] if matches else None,
            note=f"fuzzy match: {matches[0] if matches else 'none'}",
        ))

    return results


# ── Main entry point ──────────────────────────────────────────────────
def run_factuality_eval(
    insight: dict,
    metrics: dict,
    numeric_tolerance: float = 0.05,
    warn_threshold: float = 0.85,
    fail_threshold: float = 0.70,
) -> FactualityReport:

    trend_results        = metrics.get("trend_results", [])
    anomaly_results      = metrics.get("anomalies_detected", [])
    contribution_results = metrics.get("contribution_analysis", [])
    valid_entities       = _build_valid_entities(metrics)
    all_results: list[ClaimResult] = []

    # Build per-field numeric source so each insight type checks
    # against the right detector output
    field_sources = {
        "trend_insights":        {
            "numeric_pool": [t["pct_change"] for t in trend_results],
            "use_direction": True,
        },
        "anomaly_insights":      {
            "numeric_pool": [a["z_score"] for a in anomaly_results] +
                            [a["value"]   for a in anomaly_results],
            "use_direction": False,
        },
        "contribution_insights": {
            "numeric_pool": [c["contribution_pct"] for c in contribution_results] +
                            [c["delta_value"]      for c in contribution_results],
            "use_direction": False,
        },
    }

    for field_key, config in field_sources.items():
        text = insight.get(field_key, "")
        if not text:
            continue

        numeric_pool = config["numeric_pool"]

        # Numeric check against the correct pool
        for pct in _extract_percentages(text):
            if not numeric_pool:
                continue
            all_results.append(
                _check_numeric_value(pct, numeric_pool, numeric_tolerance)
            )

        # Direction check only for trend insights
        if config["use_direction"]:
            stated_dir = _extract_direction(text)

            if field_key == "trend_insights":
                if stated_dir and trend_results:
                    all_results.append(
                        _check_direction(stated_dir, text, trend_results)
                    )

            elif field_key == "anomaly_insights":
                if anomaly_results:
                    # Group anomalies by entity
                    entity_anomalies: dict[str, list] = {}
                    for a in anomaly_results:
                        entity_name = list(a["entity"].values())[0].lower()
                        entity_anomalies.setdefault(entity_name, []).append(a)

                    # For each entity mentioned in text, check its direction
                    for entity_name, anomalies in entity_anomalies.items():
                        if entity_name.lower() not in text.lower():
                            continue   # entity not mentioned in this insight

                        actual_directions = {
                            "increase" if a["z_score"] > 0 else "decrease"
                            for a in anomalies
                        }

                        # Extract direction from the sentence mentioning this entity
                        sentences = re.split(r'(?<=[.!?])\s+', text)
                        for sentence in sentences:
                            if entity_name.lower() not in sentence.lower():
                                continue
                            stated_dir = _extract_direction(sentence)
                            if not stated_dir:
                                continue
                            passed_check = stated_dir in actual_directions
                            all_results.append(ClaimResult(
                                claim_text=f"{entity_name} anomaly direction={stated_dir}",
                                check_type="direction",
                                passed=passed_check,
                                stated_value=stated_dir,
                                actual_value=str(actual_directions),
                                note=f"entity={entity_name}, actual={actual_directions}",
                            ))

        # Entity check for all fields
        all_results.extend(_check_entities(text, valid_entities))

    if not all_results:
        return FactualityReport(
            overall_score=1.0, verdict="pass",
            total_claims=0, passed_claims=0, results=[],
        )

    passed = sum(1 for r in all_results if r.passed)
    score  = passed / len(all_results)
    verdict = (
        "pass" if score >= warn_threshold else
        "warn" if score >= fail_threshold else
        "fail"
    )

    return FactualityReport(
        overall_score=score, verdict=verdict,
        total_claims=len(all_results),
        passed_claims=passed, results=all_results,
    )