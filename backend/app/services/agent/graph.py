import os
from typing import Dict, Any

from langgraph.graph import StateGraph, END
from app.config import settings
from app.services.agent.state import AgentState
from app.services.agent.nodes import (
    researcher_node,
    should_reflect_edge,
    change_detector_node,
    sentiment_analyst_node,
    report_writer_node,
)


def setup_langsmith_tracing():
    """Configures optional LangSmith tracing environment variables."""
    if settings.LANGSMITH_API_KEY:
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        os.environ["LANGCHAIN_API_KEY"] = settings.LANGSMITH_API_KEY
        os.environ["LANGCHAIN_PROJECT"] = settings.LANGSMITH_PROJECT or "competitive-intel"
        print(f"[LangSmith] Tracing enabled for project '{os.environ['LANGCHAIN_PROJECT']}'")
    else:
        os.environ.pop("LANGCHAIN_TRACING_V2", None)
        print("[LangSmith] LANGSMITH_API_KEY unset — skipping tracing gracefully.")


def build_agent_graph():
    """
    Constructs and compiles the 4-node LangGraph pipeline:
    Researcher -> [Conditional Reflection] -> Change-Detector -> Sentiment-Analyst -> Report-Writer -> END
    """
    setup_langsmith_tracing()

    builder = StateGraph(AgentState)

    # 1. Add Nodes
    builder.add_node("Researcher", researcher_node)
    builder.add_node("Change-Detector", change_detector_node)
    builder.add_node("Sentiment-Analyst", sentiment_analyst_node)
    builder.add_node("Report-Writer", report_writer_node)

    # 2. Set Entry Point
    builder.set_entry_point("Researcher")

    # 3. Add Conditional Reflection Edge after Researcher
    builder.add_conditional_edges(
        "Researcher",
        should_reflect_edge,
        {
            "Researcher": "Researcher",
            "Change-Detector": "Change-Detector",
        },
    )

    # 4. Add Sequential Edges
    builder.add_edge("Change-Detector", "Sentiment-Analyst")
    builder.add_edge("Sentiment-Analyst", "Report-Writer")
    builder.add_edge("Report-Writer", END)

    # 5. Compile Graph
    return builder.compile()


# Global compiled pipeline graph instance
agent_pipeline_graph = build_agent_graph()
