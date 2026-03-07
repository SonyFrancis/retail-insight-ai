import pandas as pd
from app.graph.builder import build_graph
from app.insights.detectors import run_detectors

if __name__ == "__main__":
    graph = build_graph()

    # initial_state = {
    #     "metrics": {"trend": "up"},
    #     "insight": "",
    #     "approved": False,
    #     "retry_count": 0
    # }


    df = pd.read_csv("app/data/raw/sales.csv", parse_dates=["date"])
    metrics = run_detectors(df)

    initial_state = {
        "metrics": metrics,
        "insight": None,
        "approved": False,
        "retry_count": 0
    }

    result = graph.invoke(initial_state)

    insight = result.get("insight", {})

    print("\n===== AI GENERATED INSIGHTS =====\n")

    print("Trend Insights:")
    print(insight.get("trend_insights", "No trend insights available."))
    print()

    print("Anomaly Insights:")
    print(insight.get("anomaly_insights", "No anomaly insights available."))
    print()

    print("Contribution Insights:")
    print(insight.get("contribution_insights", "No contribution insights available."))
    print()

    print("Confidence:", insight.get("confidence", "unknown"))

    print("\n===============================\n")