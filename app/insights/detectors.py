import pandas as pd
import numpy as np
from scipy import stats
from typing import List, Dict


# -------------------------
# Utility helpers
# -------------------------

def _add_week_col(df: pd.DataFrame):
    df = df.copy()
    df["week"] = df["date"].dt.to_period("W").astype(str)
    return df

from datetime import datetime, timedelta

def _format_week_to_natural(week_str: str) -> str:
    """
    Converts "2026-W03" to "week of Jan 12, 2026"
    Uses the Monday of that ISO week as the anchor date.
    """
    try:
        # %G = ISO year, %V = ISO week, %u = ISO weekday (1=Monday)
        dt = datetime.strptime(week_str + "-1", "%G-W%V-%u")
        return dt.strftime("week of %b %d, %Y")   # e.g. "week of Jan 12, 2026"
    except Exception:
        return week_str


def format_metrics_for_llm(metrics: dict) -> dict:
    import copy
    formatted = copy.deepcopy(metrics)

    for trend in formatted.get("trend_results", []):
        trend.pop("weekly_slope", None)     # ← remove — internal metric
        trend.pop("p_value", None)          # ← remove — not for business users
        # format time_window as before
        raw = trend.get("time_window", "")
        if "→" in raw:
            start, end = [s.strip() for s in raw.split("→")]
            trend["time_window"] = (
                f"{_format_week_to_natural(start)} to "
                f"{_format_week_to_natural(end)}"
            )

    for anomaly in formatted.get("anomalies_detected", []):
        anomaly.pop("value", None)          # ← remove raw revenue value
        anomaly.pop("z_score", None)        # ← remove — not for business users
        raw = anomaly.get("week", "")
        anomaly["week"] = _format_week_to_natural(raw)

    for contrib in formatted.get("contribution_analysis", []):
        contrib.pop("delta_value", None)    # ← remove raw delta
        raw = contrib.get("week_comparison", "")
        if "→" in raw:
            start, end = [s.strip() for s in raw.split("→")]
            contrib["week_comparison"] = (
                f"{_format_week_to_natural(start)} to "
                f"{_format_week_to_natural(end)}"
            )

    return formatted

# -------------------------
# 1. Trend Detector
# -------------------------

def detect_trends(
    df: pd.DataFrame,
    metric: str = "revenue",
    group_cols: List[str] = ["category"],
    min_pct_change: float = 0.10,
    alpha: float = 0.05,
):
    """
    Detect sustained week-over-week trends.

    Returns list of insight dicts.
    """

    df = _add_week_col(df)

    weekly = (
        df.groupby(group_cols + ["week"], as_index=False)[metric]
        .sum()
        .sort_values("week")
    )

    insights = []

    for keys, grp in weekly.groupby(group_cols):
        grp = grp.sort_values("week")

        if len(grp) < 4:
            continue

        y = grp[metric].values
        x = np.arange(len(y))

        slope, intercept, r_val, p_val, std_err = stats.linregress(x, y)

        pct_change = (y[-1] - y[0]) / max(y[0], 1)

        if abs(pct_change) >= min_pct_change and p_val <= alpha:

            direction = "increase" if pct_change > 0 else "decrease"

            insights.append(
                            {
                                "type": "trend",
                                "metric": metric,
                                "entity": dict(zip(group_cols, keys if isinstance(keys, tuple) else [keys])),
                                "direction": direction,
                                "pct_change": float(round(pct_change * 100, 2)),
                                "weekly_slope": float(round(slope, 2)),
                                "p_value": float(round(p_val, 4)),
                                "time_window": f"{grp['week'].iloc[0]} → {grp['week'].iloc[-1]}",
                            }
                        )

    return insights


# -------------------------
# 2. Anomaly Detector
# -------------------------

def detect_anomalies(
    df: pd.DataFrame,
    metric: str = "revenue",
    group_cols: List[str] = ["category"],
    z_thresh: float = 2.0,
):
    """
    Z-score based anomaly detection.
    """

    df = _add_week_col(df)

    weekly = (
        df.groupby(group_cols + ["week"], as_index=False)[metric]
        .sum()
    )

    insights = []

    for keys, grp in weekly.groupby(group_cols):

        values = grp[metric].values

        if len(values) < 10:
            continue

        z_scores = stats.zscore(values)

        for idx, z in enumerate(z_scores):

            if abs(z) >= z_thresh:

                insights.append(
                    {
                        "type": "anomaly",
                        "metric": metric,
                        "entity": dict(zip(group_cols, keys if isinstance(keys, tuple) else [keys])),
                        "week": grp["week"].iloc[idx],
                        "value": float(round(values[idx], 2)),
                        "z_score": float(round(float(z), 2)),
                    }
                )

    return insights


# -------------------------
# 3. Contribution Analysis
# -------------------------

def contribution_analysis(
    df: pd.DataFrame,
    metric: str = "revenue",
    group_col: str = "category",
):
    """
    Identify which segments contributed most to last week's change.
    """

    df = _add_week_col(df)

    weekly = (
        df.groupby([group_col, "week"], as_index=False)[metric]
        .sum()
    )

    latest_week = weekly["week"].max()

    prev_week = sorted(weekly["week"].unique())[-2]

    curr = weekly[weekly["week"] == latest_week]
    prev = weekly[weekly["week"] == prev_week]

    merged = curr.merge(prev, on=group_col, suffixes=("_curr", "_prev"))

    merged["delta"] = merged[f"{metric}_curr"] - merged[f"{metric}_prev"]

    total_change = merged["delta"].abs().sum()

    merged["contribution_pct"] = merged["delta"] / total_change * 100

    insights = []

    for _, row in merged.iterrows():

        insights.append(
            {
                "type": "contribution",
                "metric": metric,
                "entity": {group_col: row[group_col]},
                "week_comparison": f"{prev_week} → {latest_week}",
                "delta_value": float(round(row["delta"], 2)),
                "contribution_pct": float(round(row["contribution_pct"], 2)),
            }
        )

    return insights


def run_detectors(df: pd.DataFrame) -> Dict:
    
    trend = detect_trends(df)
    anomalies = detect_anomalies(df)
    contribution = contribution_analysis(df)

    # You can expand this later
    metrics = {
        "trend_results": trend,
        "anomalies_detected": anomalies,
        "contribution_analysis": contribution,
        "row_count": len(df)
    }

    return metrics


def detect_trends_batch(
    df: pd.DataFrame,
    metric: str = "revenue",
    group_cols: List[str] = ["partner_id", "category"],
    min_pct_change: float = 0.10,
    alpha: float = 0.05,
) -> Dict[str, list]:
    """
    Runs trend detection for ALL partners in one grouped pass.
    Returns dict keyed by partner_id.
    """
    df = _add_week_col(df)

    weekly = (
        df.groupby(group_cols + ["week"], as_index=False)[metric]
        .sum()
        .sort_values("week")
    )

    results_by_partner: Dict[str, list] = {}

    for keys, grp in weekly.groupby(group_cols):
        partner_id = keys[0]
        category   = keys[1]
        grp        = grp.sort_values("week")

        if len(grp) < 4:
            continue

        y = grp[metric].values
        x = np.arange(len(y))

        slope, _, _, p_val, _ = stats.linregress(x, y)
        pct_change = (y[-1] - y[0]) / max(y[0], 1)

        if abs(pct_change) >= min_pct_change and p_val <= alpha:
            direction = "increase" if pct_change > 0 else "decrease"
            results_by_partner.setdefault(partner_id, []).append({
                "type":        "trend",
                "metric":      metric,
                "entity":      {"category": category},
                "direction":   direction,
                "pct_change":  float(round(pct_change * 100, 2)),
                "weekly_slope": float(round(slope, 2)),
                "p_value":     float(round(p_val, 4)),
                "time_window": f"{grp['week'].iloc[0]} → {grp['week'].iloc[-1]}",
            })

    return results_by_partner


def detect_anomalies_batch(
    df: pd.DataFrame,
    metric: str = "revenue",
    group_cols: List[str] = ["partner_id", "category"],
    z_thresh: float = 2.0,
) -> Dict[str, list]:
    """
    Runs anomaly detection for ALL partners in one grouped pass.
    """
    df = _add_week_col(df)

    weekly = (
        df.groupby(group_cols + ["week"], as_index=False)[metric]
        .sum()
    )

    results_by_partner: Dict[str, list] = {}

    for keys, grp in weekly.groupby(group_cols):
        partner_id = keys[0]
        category   = keys[1]
        values     = grp[metric].values

        if len(values) < 10:
            continue

        z_scores = stats.zscore(values)

        for idx, z in enumerate(z_scores):
            if abs(z) >= z_thresh:
                results_by_partner.setdefault(partner_id, []).append({
                    "type":   "anomaly",
                    "metric": metric,
                    "entity": {"category": category},
                    "week":   grp["week"].iloc[idx],
                    "value":  float(round(values[idx], 2)),
                    "z_score": float(round(float(z), 2)),
                })

    return results_by_partner


def contribution_analysis_batch(
    df: pd.DataFrame,
    metric: str = "revenue",
    group_cols: List[str] = ["partner_id", "category"],
) -> Dict[str, list]:
    """
    Runs contribution analysis for ALL partners in one grouped pass.
    """
    df = _add_week_col(df)

    weekly = (
        df.groupby(group_cols + ["week"], as_index=False)[metric]
        .sum()
    )

    results_by_partner: Dict[str, list] = {}

    for partner_id, partner_grp in weekly.groupby("partner_id"):
        latest_week = partner_grp["week"].max()
        weeks       = sorted(partner_grp["week"].unique())

        if len(weeks) < 2:
            continue

        prev_week = weeks[-2]
        curr      = partner_grp[partner_grp["week"] == latest_week]
        prev      = partner_grp[partner_grp["week"] == prev_week]
        merged    = curr.merge(prev, on="category", suffixes=("_curr", "_prev"))
        merged["delta"] = (
            merged[f"{metric}_curr"] - merged[f"{metric}_prev"]
        )
        total_change = merged["delta"].abs().sum()
        merged["contribution_pct"] = merged["delta"] / total_change * 100

        for _, row in merged.iterrows():
            results_by_partner.setdefault(partner_id, []).append({
                "type":            "contribution",
                "metric":          metric,
                "entity":          {"category": row["category"]},
                "week_comparison": f"{prev_week} → {latest_week}",
                "delta_value":     float(round(row["delta"], 2)),
                "contribution_pct": float(round(row["contribution_pct"], 2)),
            })

    return results_by_partner


def run_detectors_batch(df: pd.DataFrame, metric: str = "revenue") -> Dict[str, dict]:
    """
    Single-pass batch detection for all partners.
    Returns dict keyed by partner_id — each value is the metrics dict
    expected by the LangGraph pipeline.
    """
    print("⏳ Running batch detection across all partners...")

    trends       = detect_trends_batch(df, metric)
    anomalies    = detect_anomalies_batch(df, metric)
    contribution = contribution_analysis_batch(df, metric)

    all_partners = set(trends) | set(anomalies) | set(contribution)

    batch_metrics = {}
    for partner_id in all_partners:
        batch_metrics[partner_id] = {
            "trend_results":       trends.get(partner_id, []),
            "anomalies_detected":  anomalies.get(partner_id, []),
            "contribution_analysis": contribution.get(partner_id, []),
            "row_count":           len(df[df["partner_id"] == partner_id]),
        }

    print(f"✅ Batch detection complete — {len(batch_metrics)} partners")
    return batch_metrics
