from langgraph.graph import StateGraph, END
from app.graph.state import InsightState
from app.graph.nodes import analyst_node, critic_node

def build_graph():
    workflow = StateGraph(InsightState)

    workflow.add_node("analyst", analyst_node)
    workflow.add_node("critic", critic_node)

    workflow.set_entry_point("analyst")

    workflow.add_edge("analyst", "critic")

    workflow.add_conditional_edges(
        "critic",
        lambda state: "approved" if state["approved"] else "retry",
        {
            "approved": END,
            "retry": "analyst"
        }
    )

    return workflow.compile()