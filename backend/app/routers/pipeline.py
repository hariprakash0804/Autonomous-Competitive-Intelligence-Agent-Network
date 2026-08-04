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
from app.dependencies.auth import get_current_user, get_current_user_or_api_key
from app.models.user import User
from app.models.competitor import Competitor
from app.models.agent_run import AgentRun
from app.models.report import Report
from app.config import settings
from app.services.agent.graph import invoke_pipeline_graph, flush_langsmith_tracers
from app.services.agent.state import AgentState
from app.services.reports_service import (
    render_html_report,
    render_pdf_report,
    send_slack_notification,
    send_email_notification,
)

router = APIRouter(prefix="/pipeline", tags=["pipeline"])


# Global registry to track requested cancellations for active pipeline runs
_cancelled_runs: set = set()


def is_run_cancelled(agent_run_id_str: str) -> bool:
    """Checks if an AgentRun has been marked as CANCELLED by the user."""
    if agent_run_id_str in _cancelled_runs:
        return True
    try:
        db = SessionLocal()
        run = db.get(AgentRun, uuid.UUID(agent_run_id_str))
        is_canc = run.status == "CANCELLED" if run else False
        db.close()
        return is_canc
    except Exception:
        return False


def _execute_graph_with_timeout(initial_state: AgentState) -> AgentState:
    """Helper worker to execute graph invoke inside thread pool with recursion safety net."""
    return invoke_pipeline_graph(initial_state, recursion_limit=6)


def run_agent_pipeline_task(agent_run_id_str: str, competitor_id_str: str, urls: List[str]):
    """Background worker function executing the LangGraph agent pipeline with cancellation & timeout guards."""
    import time as _time
    pipeline_start = _time.time()
    print(f"[Pipeline Task] Background worker started for AgentRun: {agent_run_id_str}", flush=True)
    db: Session = SessionLocal()
    agent_run = None
    try:
        agent_run_id = uuid.UUID(agent_run_id_str)
        agent_run = db.get(AgentRun, agent_run_id)

        # 1. Early Cancellation Check
        if is_run_cancelled(agent_run_id_str):
            print(f"[Pipeline Task] AgentRun {agent_run_id_str} was CANCELLED before start.", flush=True)
            if agent_run:
                agent_run.status = "CANCELLED"
                agent_run.completed_at = datetime.now(timezone.utc)
                db.commit()
            return

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
            "agent_run_id": agent_run_id_str,
            "status": "RUNNING",
        }

        print(f"[Pipeline Task] Invoking LangGraph graph pipeline for {len(urls)} URLs (recursion_limit=6)...", flush=True)

        # Run pipeline with configurable timeout & cancellation monitoring
        timeout_limit = float(getattr(settings, "PIPELINE_TIMEOUT_SECONDS", 600.0))
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_execute_graph_with_timeout, initial_state)
            try:
                # Poll periodically for user-triggered cancellation while task executes
                poll_start = _time.time()
                while not future.done():
                    if is_run_cancelled(agent_run_id_str):
                        print(f"[Pipeline Task] AgentRun {agent_run_id_str} CANCELLED by user mid-execution. Aborting.", flush=True)
                        if agent_run:
                            agent_run.status = "CANCELLED"
                            agent_run.completed_at = datetime.now(timezone.utc)
                            db.commit()
                        return
                    _time.sleep(0.5)
                    if _time.time() - poll_start > timeout_limit:
                        raise TimeoutError()

                final_state = future.result()
            except TimeoutError:
                elapsed = _time.time() - pipeline_start
                print(f"[Pipeline Task Error] AgentRun {agent_run_id_str} timed out after {elapsed:.1f}s ({timeout_limit:.0f}s limit)!", flush=True)
                final_state = {"reflection_triggered": False}
                if agent_run:
                    agent_run.status = "FAILED"
                    agent_run.completed_at = datetime.now(timezone.utc)
                    db.commit()
                return

        # 2. Final Cancellation Check before updating completion status
        if is_run_cancelled(agent_run_id_str):
            print(f"[Pipeline Task] AgentRun {agent_run_id_str} was CANCELLED. Skipping report delivery.", flush=True)
            if agent_run:
                agent_run.status = "CANCELLED"
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

            # Automated Multi-Channel Report Delivery on Pipeline Completion
            try:
                latest_report = (
                    db.query(Report)
                    .filter(Report.competitor_id == uuid.UUID(competitor_id_str))
                    .order_by(Report.generated_at.desc())
                    .first()
                )
                if latest_report:
                    comp = db.get(Competitor, uuid.UUID(competitor_id_str))
                    comp_name = comp.name if comp else "Competitor"
                    user_obj = comp.user if comp else None

                    # 1. Render HTML report file
                    try:
                        render_html_report(str(latest_report.id), comp_name, latest_report.summary or "")
                        print(f"[Auto-Deliver] HTML report generated for {latest_report.id}", flush=True)
                    except Exception as e_html:
                        print(f"[Auto-Deliver Note] HTML render exception: {e_html}", flush=True)

                    # 2. Render PDF report file
                    try:
                        render_pdf_report(str(latest_report.id), comp_name, latest_report.summary or "")
                        print(f"[Auto-Deliver] PDF report generated for {latest_report.id}", flush=True)
                    except Exception as e_pdf:
                        print(f"[Auto-Deliver Note] PDF render exception: {e_pdf}", flush=True)

                    # 3. Deliver Slack / Webhook notifications (dual-webhook: user profile + system env)
                    try:
                        from app.routers.reports import get_public_backend_url
                        backend_url = get_public_backend_url()
                        html_url = f"{backend_url}/reports/{latest_report.id}/html"

                        user_webhook = (user_obj.slack_webhook_url or "").strip() if user_obj and getattr(user_obj, "slack_webhook_url", None) else None
                        env_webhook = (
                            os.getenv("SLACK_WEBHOOK_URL")
                            or os.getenv("WEBHOOK_URL")
                            or getattr(settings, "SLACK_WEBHOOK_URL", None)
                            or getattr(settings, "WEBHOOK_URL", None)
                            or ""
                        ).strip() or None

                        target_webhooks = []
                        if user_webhook and user_webhook.startswith("http"):
                            target_webhooks.append(user_webhook)
                        if env_webhook and env_webhook.startswith("http") and env_webhook not in target_webhooks:
                            target_webhooks.append(env_webhook)

                        for w_url in target_webhooks:
                            send_slack_notification(
                                webhook_url=w_url,
                                competitor_name=comp_name,
                                report_summary=latest_report.summary or "",
                                html_report_url=html_url,
                            )
                        if target_webhooks:
                            print(f"[Auto-Deliver] Slack notifications sent to {len(target_webhooks)} webhooks.", flush=True)
                    except Exception as e_slack:
                        print(f"[Auto-Deliver Note] Slack delivery exception: {e_slack}", flush=True)

                    # 4. Deliver Email notification if user email exists
                    if user_obj and user_obj.email:
                        try:
                            from app.routers.reports import get_public_backend_url
                            backend_url = get_public_backend_url()
                            html_url = f"{backend_url}/reports/{latest_report.id}/html"
                            send_email_notification(
                                recipient_email=user_obj.email,
                                competitor_name=comp_name,
                                markdown_report=latest_report.summary or "",
                                html_report_url=html_url,
                            )
                            print(f"[Auto-Deliver] Email report dispatched to {user_obj.email}.", flush=True)
                        except Exception as e_email:
                            print(f"[Auto-Deliver Note] Email delivery note: {e_email}", flush=True)
            except Exception as e_auto:
                print(f"[Auto-Deliver Error] Automated delivery task exception: {e_auto}", flush=True)

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


@router.get("/runs")
def list_pipeline_runs(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user_or_api_key)],
):
    """Lists all agent pipeline runs for the current user, ordered by most recent first."""
    runs = (
        db.query(AgentRun)
        .join(Competitor, AgentRun.competitor_id == Competitor.id)
        .filter(Competitor.user_id == current_user.id)
        .order_by(AgentRun.started_at.desc())
        .limit(100)
        .all()
    )
    return [
        {
            "id": str(run.id),
            "competitor_id": str(run.competitor_id),
            "competitor_name": run.competitor.name if run.competitor else "",
            "status": run.status,
            "started_at": run.started_at.isoformat() if run.started_at else None,
            "completed_at": run.completed_at.isoformat() if run.completed_at else None,
            "reflection_triggered": run.reflection_triggered,
            "execution_logs": run.execution_logs or [],
            "pages_visited": run.pages_visited or [],
        }
        for run in runs
    ]


@router.post("/run/{competitor_id}")
def start_pipeline_run(
    competitor_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user_or_api_key)],
):
    """
    Triggers the 4-node LangGraph agent pipeline asynchronously using FastAPI BackgroundTasks.
    Returns HTTP 202 immediately with status="RUNNING".
    """
    competitor = db.get(Competitor, competitor_id)
    if not competitor or competitor.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Competitor not found")

    # Collect URLs to scrape (both user's company URL and competitor URLs)
    urls = []
    seen_urls = set()

    def _add_url(u: str):
        u = u.strip()
        if u and u not in seen_urls:
            seen_urls.add(u)
            urls.append(u)

    # 1. User's own company URL + pricing & homepage (equal treatment as competitor)
    user_url = getattr(current_user, "company_url", None)
    if user_url and user_url.strip():
        _add_url(user_url.strip())
        # Derive pricing URL and homepage for user's company (same as competitor treatment)
        from urllib.parse import urlparse as _urlparse
        _parsed_user = _urlparse(user_url.strip())
        if _parsed_user.netloc:
            user_homepage = f"{_parsed_user.scheme or 'https'}://{_parsed_user.netloc}/"
            _add_url(user_homepage + "pricing")

    # 2. Competitor's company URL
    if competitor.company_url:
        _add_url(competitor.company_url.strip())

    # 3. Competitor's pricing URL & root homepage
    if competitor.pricing_url:
        _add_url(competitor.pricing_url.strip())
        from urllib.parse import urlparse
        parsed = urlparse(competitor.pricing_url.strip())
        if parsed.netloc:
            competitor_homepage = f"{parsed.scheme or 'https'}://{parsed.netloc}/"
            _add_url(competitor_homepage)

    review_sources = list(competitor.review_urls) if competitor.review_urls else []
    if not review_sources:
        c_name_clean = competitor.name.lower().replace(" ", "-")
        if competitor.domain:
            review_sources.append(f"https://www.trustpilot.com/review/{competitor.domain}")
        review_sources.append(f"https://www.g2.com/products/{c_name_clean}/reviews")
        review_sources.append(f"https://www.google.com/search?q={competitor.name}+customer+reviews+and+ratings")

    for ru in review_sources[:3]:
        if ru:
            _add_url(ru)

    if competitor.news_keywords:
        for kw in competitor.news_keywords:
            if kw and (kw.strip().startswith("http://") or kw.strip().startswith("https://")):
                _add_url(kw)

    if not urls:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No valid URLs found for competitor. Please specify a company URL, pricing URL, or review URLs."
        )

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
    current_user: Annotated[User, Depends(get_current_user_or_api_key)],
):
    """Retrieves status of a background agent run for UI polling with strict user ownership check."""
    agent_run = db.get(AgentRun, agent_run_id)
    if not agent_run or not agent_run.competitor or agent_run.competitor.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent run not found")

    return {
        "id": str(agent_run.id),
        "competitor_id": str(agent_run.competitor_id),
        "status": agent_run.status,
        "started_at": agent_run.started_at.isoformat(),
        "completed_at": agent_run.completed_at.isoformat() if agent_run.completed_at else None,
        "reflection_triggered": agent_run.reflection_triggered,
        "langsmith_trace_url": agent_run.langsmith_trace_url,
        "execution_logs": agent_run.execution_logs or [],
        "pages_visited": agent_run.pages_visited or [],
    }


@router.get("/logs/{agent_run_id}")
def get_pipeline_logs(
    agent_run_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user_or_api_key)],
):
    """Returns detailed user-facing agent run execution logs and visited pages list."""
    agent_run = db.get(AgentRun, agent_run_id)
    if not agent_run or not agent_run.competitor or agent_run.competitor.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent run not found")

    return {
        "id": str(agent_run.id),
        "competitor_id": str(agent_run.competitor_id),
        "competitor_name": agent_run.competitor.name if agent_run.competitor else "",
        "status": agent_run.status,
        "started_at": agent_run.started_at.isoformat() if agent_run.started_at else None,
        "completed_at": agent_run.completed_at.isoformat() if agent_run.completed_at else None,
        "workflow_name": "4-Node LangGraph Pipeline (Researcher -> Change-Detector -> Sentiment-Analyst -> Report-Writer)",
        "pages_visited": agent_run.pages_visited or [],
        "execution_logs": agent_run.execution_logs or [],
    }


@router.post("/cancel/{agent_run_id}")
@router.post("/{agent_run_id}/cancel")
def cancel_pipeline_run(
    agent_run_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user_or_api_key)],
):
    """Cancels an ongoing background agent pipeline run."""
    agent_run = db.get(AgentRun, agent_run_id)
    if not agent_run or not agent_run.competitor or agent_run.competitor.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent run not found")

    run_id_str = str(agent_run_id)
    _cancelled_runs.add(run_id_str)

    if agent_run.status in ("RUNNING", "PENDING"):
        agent_run.status = "CANCELLED"
        agent_run.completed_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(agent_run)
        print(f"[Pipeline Cancel] AgentRun {run_id_str} marked as CANCELLED by user.", flush=True)

    return {
        "id": str(agent_run.id),
        "status": agent_run.status,
        "message": "Pipeline run cancellation requested.",
    }
