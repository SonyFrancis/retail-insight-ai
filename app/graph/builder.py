from langgraph.graph import StateGraph, END
from app.graph.state import InsightState
from app.graph.nodes import analyst_node, critic_node, eval_node

MAX_RETRIES = 2

def _route_after_eval(state):
    report = state.get("factuality_report")
    if report and report.verdict == "fail":
        if state["retry_count"] < MAX_RETRIES:
            return "retry"
    return "approved"

def build_graph():
    workflow = StateGraph(InsightState)

    workflow.add_node("analyst", analyst_node)
    workflow.add_node("critic", critic_node)
    workflow.add_node("eval",    eval_node)   

    workflow.set_entry_point("analyst")
    workflow.add_edge("analyst", "critic")
    workflow.add_conditional_edges(
        "critic",
        lambda state: "approved" if state["approved"] else "retry",
        {
            "approved": "eval",
            "retry": "analyst"
        }
    )
    # workflow.add_edge("eval", END)

    workflow.add_conditional_edges(
        "eval",
        _route_after_eval,
        {
            "approved": END,
            "retry":    "analyst"
        }
    )
    return workflow.compile()