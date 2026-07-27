import os
import sys
import uuid
import traceback
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from typing import Annotated, List, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.database import get_db, SessionLocal
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.models.competitor import Competitor
from app.models.agent_run import AgentRun
from app.services.agent.graph import invoke_pipeline_graph, flush_langsmith_tracers
from app.services.agent.state import AgentState

router = APIRouter(prefix="/pipeline", tags=["pipeline"])


def _execute_graph_with_timeout(initial_state: AgentState) -> AgentState:
    """Helper worker to execute graph invoke inside thread pool with recursion safety net."""
    return invoke_pipeline_graph(initial_state, recursion_limit=6)


def run_agent_pipeline_task(agent_run_id_str: str, competitor_id_str: str, urls: List[str]):
    """Background worker function executing the LangGraph agent pipeline with a 120-second timeout guard."""
    import time as _time
    pipeline_start = _time.time()
    print(f"[Pipeline Task] Background worker started for AgentRun: {agent_run_id_str}", flush=True)
    db: Session = SessionLocal()
    agent_run = None
    try:
        agent_run_id = uuid.UUID(agent_run_id_str)
        agent_run = db.get(AgentRun, agent_run_id)

        initial_state: AgentState = {
            "competitor_id": competitor_id_str,
            "competitor_name": "",
            "urls": urls,
            "raw_pages": [],
            "prev_snapshot": None,
            "diffs": [],
            "sentiment_results": [],
            "report_draft": "",
            "retry_count": 0,
            "reflection_triggered": False,
            "is_incomplete": False,
            "status": "RUNNING",
        }

        print(f"[Pipeline Task] Invoking LangGraph graph pipeline for {len(urls)} URLs (recursion_limit=6)...", flush=True)

        # Run pipeline with a 120s hard timeout guard to account for LLM generation & rate-limiting delays
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_execute_graph_with_timeout, initial_state)
            try:
                final_state = future.result(timeout=120.0)
            except TimeoutError:
                elapsed = _time.time() - pipeline_start
                print(f"[Pipeline Task Error] AgentRun {agent_run_id_str} timed out after {elapsed:.1f}s hard limit!", flush=True)
                final_state = {"reflection_triggered": False}
                if agent_run:
                    agent_run.status = "FAILED"
                    agent_run.completed_at = datetime.now(timezone.utc)
                    db.commit()
                return

        # Update AgentRun in PostgreSQL
        if agent_run:
            agent_run.status = "COMPLETED"
            agent_run.completed_at = datetime.now(timezone.utc)
            agent_run.reflection_triggered = final_state.get("reflection_triggered", False)
            agent_run.langsmith_trace_url = (
                f"https://smith.langchain.com/o/default/projects/p/{agent_run_id}"
                if os.environ.get("LANGCHAIN_TRACING_V2") == "true"
                else None
            )
            db.commit()
            elapsed = _time.time() - pipeline_start
            print(f"[Pipeline Task] AgentRun {agent_run_id_str} COMPLETED in {elapsed:.1f}s!", flush=True)

    except Exception as exc:
        elapsed = _time.time() - pipeline_start
        print(f"[Pipeline Task Error] Agent pipeline failed after {elapsed:.1f}s: {exc}", flush=True)
        traceback.print_exc(file=sys.stdout)
        if agent_run:
            agent_run.status = "FAILED"
            agent_run.completed_at = datetime.now(timezone.utc)
            db.commit()
    finally:
        flush_langsmith_tracers()
        db.close()


@router.post("/run/{competitor_id}")
def start_pipeline_run(
    competitor_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Triggers the 4-node LangGraph agent pipeline asynchronously using FastAPI BackgroundTasks.
    Returns HTTP 202 immediately with status="RUNNING".
    """
    competitor = db.get(Competitor, competitor_id)
    if not competitor or competitor.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Competitor not found")

    # Collect URLs to scrape
    urls = []
    if competitor.pricing_url:
        urls.append(competitor.pricing_url)
    if competitor.review_urls:
        for ru in competitor.review_urls:
            if ru and ru.strip():
                urls.append(ru.strip())
    if competitor.news_keywords:
        for kw in competitor.news_keywords:
            if kw and (kw.strip().startswith("http://") or kw.strip().startswith("https://")):
                urls.append(kw.strip())

    # Fallback default pricing URL if empty
    if not urls:
        urls.append("https://github.com/pricing")

    # Create AgentRun database record
    agent_run = AgentRun(
        competitor_id=competitor_id,
        status="RUNNING",
        started_at=datetime.now(timezone.utc),
        reflection_triggered=False,
    )
    db.add(agent_run)
    db.commit()
    db.refresh(agent_run)

    print(f"[Pipeline Trigger] Dispatched background task for run {agent_run.id} ({competitor.name})", flush=True)

    # Schedule background execution
    background_tasks.add_task(
        run_agent_pipeline_task,
        str(agent_run.id),
        str(competitor_id),
        urls,
    )

    return {
        "agent_run_id": str(agent_run.id),
        "competitor_id": str(competitor_id),
        "status": "RUNNING",
        "started_at": agent_run.started_at.isoformat(),
        "message": "Agent pipeline execution started in background",
    }


@router.get("/status/{agent_run_id}")
def get_pipeline_status(
    agent_run_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Retrieves status of a background agent run for UI polling."""
    agent_run = db.get(AgentRun, agent_run_id)
    if not agent_run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent run not found")

    return {
        "id": str(agent_run.id),
        "competitor_id": str(agent_run.competitor_id),
        "status": agent_run.status,
        "started_at": agent_run.started_at.isoformat(),
        "completed_at": agent_run.completed_at.isoformat() if agent_run.completed_at else None,
        "reflection_triggered": agent_run.reflection_triggered,
        "langsmith_trace_url": agent_run.langsmith_trace_url,
    }
