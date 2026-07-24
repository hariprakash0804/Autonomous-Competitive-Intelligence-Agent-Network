import os
import sys
import uuid
import json
from datetime import datetime, timezone
from pathlib import Path

# Fix Windows console UTF-8 output encoding
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

# Add backend directory to sys.path and load .env overrides first
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from dotenv import load_dotenv
load_dotenv(backend_dir / ".env", override=True)

import app.config as config_module
config_module.settings = config_module.Settings()

from sqlalchemy import select
from app.database import SessionLocal
from app.models.competitor import Competitor
from app.models.agent_run import AgentRun
from app.models.report import Report
from app.services.agent.graph import agent_pipeline_graph, build_agent_graph
from app.services.agent.state import AgentState
import app.services.agent.nodes as nodes_module


def print_graph_code_definition():
    print("=========================================================================")
    print("1. LANGGRAPH GRAPH DEFINITION (ACTUAL CODE)")
    print("=========================================================================\n")
    
    graph_file = Path(__file__).resolve().parent.parent / "app" / "services" / "agent" / "graph.py"
    nodes_file = Path(__file__).resolve().parent.parent / "app" / "services" / "agent" / "nodes.py"

    print("--- [graph.py] ---")
    with open(graph_file, "r", encoding="utf-8") as f:
        print(f.read())

    print("\n--- [nodes.py (Reflection Edge Code Snippet)] ---")
    with open(nodes_file, "r", encoding="utf-8") as f:
        lines = f.readlines()
        in_edge = False
        for line in lines:
            if "def should_reflect_edge" in line:
                in_edge = True
            if in_edge:
                print(line, end="")
                if "return \"Change-Detector\"" in line:
                    break


def run_pipeline_with_reflection_test():
    db = SessionLocal()
    try:
        competitor = db.scalars(select(Competitor).where(Competitor.name == "GitHub")).first()
        if not competitor:
            print("Seeded competitor 'GitHub' not found. Run seed_data.py first.")
            return

        print("\n=========================================================================")
        print("2. LANGGRAPH PIPELINE RUN WITH TRIGGERED REFLECTION EDGE LOGS")
        print("=========================================================================\n")

        agent_run = AgentRun(
            competitor_id=competitor.id,
            status="RUNNING",
            started_at=datetime.now(timezone.utc),
            reflection_triggered=False,
        )
        db.add(agent_run)
        db.commit()
        db.refresh(agent_run)

        urls = [
            "https://github.com/pricing",
            "https://client.schwab.com/",  # Triggers is_stale=True (JS shell)
            "https://github.blog/",
        ]

        initial_state: AgentState = {
            "competitor_id": str(competitor.id),
            "competitor_name": competitor.name,
            "urls": urls,
            "raw_pages": [],
            "prev_snapshot": None,
            "diffs": [],
            "sentiment_results": [],
            "report_draft": "",
            "model_used": None,
            "retry_count": 0,
            "reflection_triggered": False,
            "is_incomplete": False,
            "status": "RUNNING",
        }

        print(f"Initial State: competitor_id={competitor.id}, retry_count=0, urls_count={len(urls)}")
        print("Starting LangGraph execution...\n")

        final_state = agent_pipeline_graph.invoke(initial_state)

        agent_run.status = "COMPLETED"
        agent_run.completed_at = datetime.now(timezone.utc)
        agent_run.reflection_triggered = final_state.get("reflection_triggered", False)
        db.commit()
        db.refresh(agent_run)

        print("\n--- Pipeline Execution Step Summary ---")
        print(f"Retry Count Executed   : {final_state.get('retry_count')}")
        print(f"Reflection Triggered   : {final_state.get('reflection_triggered')}")
        print(f"Is Incomplete Flag     : {final_state.get('is_incomplete')}")
        print(f"LLM Model Served       : {final_state.get('model_used')}")
        print(f"Diffs Detected Count   : {len(final_state.get('diffs', []))}")
        print(f"Sentiment Items Count  : {len(final_state.get('sentiment_results', []))}")

        print("\n=========================================================================")
        print("3. RESULTING agent_runs ROW IN POSTGRESQL")
        print("=========================================================================")
        print(f"ID                   : {agent_run.id}")
        print(f"Competitor ID        : {agent_run.competitor_id}")
        print(f"Status               : {agent_run.status}")
        print(f"Started At           : {agent_run.started_at}")
        print(f"Completed At         : {agent_run.completed_at}")
        print(f"Reflection Triggered : {agent_run.reflection_triggered}")
        print(f"LangSmith Trace URL  : {agent_run.langsmith_trace_url}")

        print("\n=========================================================================")
        print("4. STRUCTURED OUTPUT OF REPORT-WRITER NODE (OPENROUTER LLM)")
        print("=========================================================================\n")
        report_text = final_state.get("report_draft", "No report draft generated.")
        print(report_text)

        print("\n=========================================================================")
        print("PHASE 3 STOP GATE VERIFICATION COMPLETE")
        print("=========================================================================")

    finally:
        db.close()


if __name__ == "__main__":
    print_graph_code_definition()
    run_pipeline_with_reflection_test()
