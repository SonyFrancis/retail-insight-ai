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