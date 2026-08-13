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


import threading
import gc

# 512 MB RAM Memory Guard: Restrict concurrent active pipelines on low-memory tiers (e.g. Render free plan)
MAX_CONCURRENT_PIPELINES = int(os.getenv("MAX_CONCURRENT_PIPELINES", "1"))
_pipeline_semaphore = threading.Semaphore(MAX_CONCURRENT_PIPELINES)

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
    """Background worker function executing the LangGraph agent pipeline with cancellation, memory queuing & timeout guards."""
    import time as _time
    print(f"[Pipeline Task] Task queued for AgentRun {agent_run_id_str}. Waiting for execution slot...", flush=True)

    with _pipeline_semaphore:
        pipeline_start = _time.time()
        print(f"[Pipeline Task] Slot acquired! Starting pipeline execution for AgentRun: {agent_run_id_str}", flush=True)
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
                "feature_diffs": [],
                "sentiment_results": [],
                "report_draft": "",
                "model_used": None,
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
            try:
                db.close()
            except Exception:
                pass
            gc.collect()
            print(f"[Pipeline Task] Cleaned up DB session & released RAM for AgentRun {agent_run_id_str}.", flush=True)


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

    def _normalize_url(u: str) -> str:
        """Normalizes a URL for deduplication: adds scheme, strips trailing slash, fragments, and tracking params."""
        u = u.strip()
        if not u:
            return ""
        # Add scheme if missing
        if not u.startswith(("http://", "https://")):
            u = "https://" + u
        from urllib.parse import urlparse, urlunparse, unquote, parse_qs, urlencode
        try:
            u = unquote(u)  # Decode %20-style encoding
            parsed = urlparse(u)
            # Strip fragment
            # Strip tracking query params (utm_*, ref, source, etc.) but keep meaningful ones
            tracking_prefixes = ("utm_", "ref", "source", "campaign", "fbclid", "gclid", "mc_")
            if parsed.query:
                params = parse_qs(parsed.query, keep_blank_values=True)
                clean_params = {k: v for k, v in params.items() if not any(k.lower().startswith(tp) for tp in tracking_prefixes)}
                clean_query = urlencode(clean_params, doseq=True) if clean_params else ""
            else:
                clean_query = ""
            # Rebuild with clean path (strip trailing slash), no fragment
            clean_path = parsed.path.rstrip("/") or "/"
            normalized = urlunparse((parsed.scheme, parsed.netloc.lower(), clean_path, parsed.params, clean_query, ""))
            return normalized
        except Exception:
            return u.rstrip("/")

    def _add_url(u: str):
        normalized = _normalize_url(u)
        if normalized and normalized not in seen_urls:
            seen_urls.add(normalized)
            urls.append(normalized)

    def _extract_domain(url_str: str) -> str:
        if not url_str:
            return ""
        u = url_str.strip()
        if not u.startswith(("http://", "https://")):
            u = "https://" + u
        from urllib.parse import urlparse
        try:
            d = (urlparse(u).netloc or "").lower().split(":")[0]
            return d[4:] if d.startswith("www.") else d
        except Exception:
            return ""

    # Common pricing subpath probe endpoints (probed symmetrically for both companies).
    # Only the 2 most universally valid paths are probed here to avoid 404 noise.
    # Deeper pricing URL discovery (e.g., /api/pricing, /product/pricing, /enterprise/pricing)
    # happens in the researcher node's Pass 2 via generate_pricing_probe_urls() after
    # homepage link analysis confirms which paths actually exist.
    PRICING_PROBE_PATHS = [
        "/pricings",
        "/plans",
    ]

    # ═════════════════════════════════════════════════════════════════════════
    # 1. USER COMPANY DATA COLLECTION (Symmetrical to Competitor)
    # ═════════════════════════════════════════════════════════════════════════
    user_company_name = getattr(current_user, "company_name", None) or "Our Company"
    user_url = getattr(current_user, "company_url", None)
    user_domain = _extract_domain(user_url)

    if user_url and user_url.strip():
        # A. User Homepage
        _add_url(user_url.strip())
        from urllib.parse import urlparse, quote, quote_plus
        u_parsed = urlparse(_normalize_url(user_url.strip()))
        if u_parsed.netloc:
            u_base = f"{u_parsed.scheme or 'https'}://{u_parsed.netloc}"
            # B. User Pricing & Plan Probes
            for probe_path in PRICING_PROBE_PATHS[:5]:  # Probe top 5 pricing paths for user
                _add_url(f"{u_base}{probe_path}")

        if user_domain:
            # C. User Customer Review Sources (Trustpilot, G2 direct links)
            # NOTE: Google Search URLs are removed because Google always blocks automated
            # requests with CAPTCHAs. Direct Trustpilot/G2 links are far more effective.
            _add_url(f"https://www.trustpilot.com/review/{quote(user_domain)}")
            # Direct G2 product URL (slug format: lowercase, hyphenated company name)
            import re as _re
            g2_user_slug = _re.sub(r"[^\w\s-]", "", user_company_name.lower()).strip().replace(" ", "-")
            if g2_user_slug:
                _add_url(f"https://www.g2.com/products/{quote(g2_user_slug)}/reviews")

            # D. User Company Market News Search (routed through Jina Reader automatically)
            news_user_q = quote_plus(user_company_name)
            _add_url(f"https://news.google.com/search?q={news_user_q}&hl=en-US")

    # ═════════════════════════════════════════════════════════════════════════
    # 2. COMPETITOR TARGET DATA COLLECTION (Symmetrical to User Company)
    # ═════════════════════════════════════════════════════════════════════════
    comp_company_url = ""
    comp_domain = ""

    if competitor.company_url:
        c_dom = _extract_domain(competitor.company_url)
        if c_dom and c_dom != user_domain:
            comp_company_url = competitor.company_url.strip()
            comp_domain = c_dom

    if not comp_company_url and competitor.pricing_url:
        p_dom = _extract_domain(competitor.pricing_url)
        if p_dom and p_dom != user_domain:
            comp_domain = p_dom
            from urllib.parse import urlparse
            p_parsed = urlparse(_normalize_url(competitor.pricing_url.strip()))
            comp_company_url = f"{p_parsed.scheme or 'https'}://{p_parsed.netloc}/"

    if not comp_domain and competitor.domain:
        c_dom = _extract_domain(competitor.domain)
        if c_dom and c_dom != user_domain:
            comp_domain = c_dom
            if not comp_company_url:
                comp_company_url = f"https://www.{comp_domain}" if "." in comp_domain else f"https://{comp_domain}.com"

    # A. Competitor Homepage & Pricing Subpath Probes
    if comp_company_url:
        _add_url(comp_company_url)
        from urllib.parse import urlparse
        parsed = urlparse(_normalize_url(comp_company_url))
        if parsed.netloc and not competitor.pricing_url:
            base_site = f"{parsed.scheme or 'https'}://{parsed.netloc}"
            for probe_path in PRICING_PROBE_PATHS:
                _add_url(f"{base_site}{probe_path}")

    # B. Competitor Explicit Pricing URL
    if competitor.pricing_url:
        _add_url(competitor.pricing_url.strip())

    # C. Competitor Customer Review Sources (Trustpilot, G2 direct links)
    # NOTE: Google Search URLs are removed — Google always blocks with CAPTCHAs.
    # Direct Trustpilot/G2 product URLs are far more reliable for review collection.
    review_sources = list(competitor.review_urls) if competitor.review_urls else []
    if not review_sources:
        from urllib.parse import quote, quote_plus
        import re as _re

        if comp_domain:
            review_sources.append(f"https://www.trustpilot.com/review/{quote(comp_domain)}")
        # Direct G2 product URL (slug format: lowercase, hyphenated name)
        g2_slug = _re.sub(r"[^\w\s-]", "", competitor.name.lower()).strip().replace(" ", "-")
        if g2_slug:
            review_sources.append(f"https://www.g2.com/products/{quote(g2_slug)}/reviews")

    for ru in review_sources[:3]:
        if ru:
            _add_url(ru)

    # D. Competitor Market News Search
    if competitor.news_keywords:
        from urllib.parse import quote_plus
        for kw in competitor.news_keywords:
            if not kw or not kw.strip():
                continue
            kw_clean = kw.strip()
            if kw_clean.startswith(("http://", "https://")):
                _add_url(kw_clean)
            else:
                _add_url(f"https://news.google.com/search?q={quote_plus(kw_clean)}&hl=en-US")
    else:
        from urllib.parse import quote_plus
        comp_news_q = quote_plus(competitor.name)
        _add_url(f"https://news.google.com/search?q={comp_news_q}&hl=en-US")

    if not urls and not (competitor.description_text and competitor.description_text.strip()):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No valid URLs or document/text details found for competitor. Please specify a company URL, pricing URL, or upload a document."
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


@router.post("/trigger-all")
def trigger_all_pipelines(
    background_tasks: BackgroundTasks,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user_or_api_key)],
):
    """
    Triggers background agent pipelines for ALL competitor targets owned by the current user.
    Executes sequentially under memory queue control (Render 512 MB optimization).
    """
    competitors = db.scalars(
        select(Competitor).where(Competitor.user_id == current_user.id)
    ).all()

    if not competitors:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No competitor targets found for your account. Please add a competitor target first."
        )

    runs_created = []
    for competitor in competitors:
        try:
            urls = []
            def _add_url(u: str):
                if u and isinstance(u, str):
                    clean = u.strip()
                    if clean and clean not in urls:
                        urls.append(clean)

            if current_user.company_url:
                _add_url(current_user.company_url.strip())
            if competitor.company_url:
                _add_url(competitor.company_url.strip())
            if competitor.pricing_url:
                _add_url(competitor.pricing_url.strip())

            if not urls and not (competitor.description_text and competitor.description_text.strip()):
                continue

            agent_run = AgentRun(
                competitor_id=competitor.id,
                status="RUNNING",
                started_at=datetime.now(timezone.utc),
                reflection_triggered=False,
            )
            db.add(agent_run)
            db.commit()
            db.refresh(agent_run)

            background_tasks.add_task(
                run_agent_pipeline_task,
                str(agent_run.id),
                str(competitor.id),
                urls,
            )

            runs_created.append({
                "agent_run_id": str(agent_run.id),
                "competitor_id": str(competitor.id),
                "competitor_name": competitor.name,
                "status": "RUNNING",
            })
        except Exception as e:
            print(f"[Trigger All Error] Failed to trigger run for competitor {competitor.name}: {e}")

    return {
        "status": "QUEUED",
        "total_triggered": len(runs_created),
        "message": f"Queued pipeline analysis for {len(runs_created)} competitor target(s). Executes sequentially to maintain low RAM footprint.",
        "runs": runs_created,
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
