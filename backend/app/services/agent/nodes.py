import uuid
import time
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Any, List

from sqlalchemy.orm import Session
from sqlalchemy import select

from app.database import SessionLocal
from app.models.competitor import Competitor
from app.models.snapshot import Snapshot, SourceType
from app.models.price_change import PriceChange
from app.models.sentiment_score import SentimentScore
from app.models.report import Report
from app.services.scraper import scrape_url
from app.services.diff_pricing import diff_pricing
from app.services.sentiment import sentiment_score
from app.services.vector_store import vector_store
from app.services.llm import generate_executive_report
from app.services.agent.state import AgentState


def researcher_node(state: AgentState) -> AgentState:
    """
    1. Researcher Node:
       Increments retry_count and fetches all registered competitor URLs in parallel using ThreadPoolExecutor.
       Calls scraper.py directly for scraping and staleness evaluation.
       Uses batched DB commits and deferred FAISS saves for performance.
    """
    node_start = time.time()
    print(f"[Researcher Node] Starting...", flush=True)

    if state.get("retry_count", 0) >= 1:
        state["reflection_triggered"] = True

    state["retry_count"] = state.get("retry_count", 0) + 1
    urls = state.get("urls", [])

    db: Session = SessionLocal()
    try:
        competitor_id = uuid.UUID(state["competitor_id"])
        competitor = db.get(Competitor, competitor_id)
        if competitor:
            state["competitor_name"] = competitor.name

        # Parallel scraping using ThreadPoolExecutor
        scrape_start = time.time()
        if urls:
            with ThreadPoolExecutor(max_workers=min(len(urls), 5)) as executor:
                raw_pages = list(executor.map(scrape_url, urls))
        else:
            raw_pages = []
        print(f"[Researcher Node] Scraping {len(urls)} URLs completed in {time.time() - scrape_start:.2f}s", flush=True)

        # Record snapshots in DB & FAISS if valid — batched commits
        db_start = time.time()
        snapshots_to_index = []
        for scrape_res in raw_pages:
            url = scrape_res.get("url", "")
            if competitor and not scrape_res["is_stale"] and scrape_res["clean_text"]:
                source_type = SourceType.PRICING if "pricing" in url.lower() else (
                    SourceType.REVIEW if "review" in url.lower() or "about" in url.lower() or "docs" in url.lower() else SourceType.NEWS
                )

                snapshot = Snapshot(
                    competitor_id=competitor.id,
                    source_type=source_type,
                    raw_content=scrape_res["clean_text"],
                    content_hash=scrape_res["content_hash"],
                    is_stale=False,
                    fetched_at=datetime.now(timezone.utc),
                )
                db.add(snapshot)
                db.flush()  # Get snapshot.id without committing — batched

                snapshots_to_index.append((snapshot, source_type, scrape_res["clean_text"]))

        # Single batch commit for all snapshots
        if snapshots_to_index:
            db.commit()
        print(f"[Researcher Node] DB batch commit ({len(snapshots_to_index)} snapshots) in {time.time() - db_start:.2f}s", flush=True)

        # FAISS indexing with deferred save — single flush at end
        faiss_start = time.time()
        for snapshot, source_type, clean_text in snapshots_to_index:
            vector_store.add_snapshot_chunks(
                snapshot_id=str(snapshot.id),
                competitor_id=str(competitor.id),
                source_type=source_type.value,
                fetched_at=snapshot.fetched_at.isoformat(),
                text=clean_text,
                defer_save=True,
            )
        if snapshots_to_index:
            vector_store.flush()
        print(f"[Researcher Node] FAISS indexing + flush in {time.time() - faiss_start:.2f}s", flush=True)

    finally:
        db.close()

    state["raw_pages"] = raw_pages
    print(f"[Researcher Node] TOTAL: {time.time() - node_start:.2f}s", flush=True)
    return state


def should_reflect_edge(state: AgentState) -> str:
    """
    Conditional Reflection Edge: Pure routing function.
    If any page is_stale and retry_count < 2, loop back to Researcher node for a retry pass.
    Otherwise proceed to Parallel-Analysis node.
    """
    has_stale = any(page.get("is_stale", False) for page in state.get("raw_pages", []))

    if has_stale and state.get("retry_count", 0) < 2:
        return "Researcher"

    return "Parallel-Analysis"


def change_detector_node(state: AgentState) -> AgentState:
    """
    2. Change-Detector Node:
       Sets is_incomplete flag if max retries were hit with stale pages,
       and compares pricing pages using Phase 2 diff_pricing service.
    """
    node_start = time.time()
    print(f"[Change-Detector] Starting...", flush=True)

    has_stale = any(page.get("is_stale", False) for page in state.get("raw_pages", []))
    if has_stale and state.get("retry_count", 0) >= 2:
        state["is_incomplete"] = True

    diffs = []
    db: Session = SessionLocal()
    try:
        competitor_id = uuid.UUID(state["competitor_id"])
        
        # Get prior pricing snapshot
        stmt = (
            select(Snapshot)
            .where(
                Snapshot.competitor_id == competitor_id,
                Snapshot.source_type == SourceType.PRICING,
            )
            .order_by(Snapshot.fetched_at.desc())
        )
        snapshots = db.scalars(stmt).all()
        prev_text = snapshots[1].raw_content if len(snapshots) > 1 else ""

        for page in state.get("raw_pages", []):
            if "pricing" in page.get("url", "").lower() and not page.get("is_stale"):
                # Call Phase 2 diff_pricing directly
                detected_diffs = diff_pricing(prev_text, page["clean_text"])
                diffs.extend(detected_diffs)

                # Persist price changes in DB
                for d in detected_diffs:
                    pc = PriceChange(
                        competitor_id=competitor_id,
                        snapshot_before_id=snapshots[1].id if len(snapshots) > 1 else None,
                        snapshot_after_id=snapshots[0].id if len(snapshots) > 0 else None,
                        tier_name=d.get("tier_name"),
                        old_price=d.get("old_price") if isinstance(d.get("old_price"), (int, float)) else None,
                        new_price=d.get("new_price") if isinstance(d.get("new_price"), (int, float)) else None,
                        detected_at=datetime.now(timezone.utc),
                    )
                    db.add(pc)
                db.commit()
    finally:
        db.close()

    state["diffs"] = diffs
    print(f"[Change-Detector] TOTAL: {time.time() - node_start:.2f}s", flush=True)
    return state


def sentiment_analyst_node(state: AgentState) -> AgentState:
    """
    3. Sentiment-Analyst Node:
       Analyzes review and news pages using Phase 2 sentiment_score service function directly.
       Uses a single pre-fetched snapshot and batched DB commit for performance.
    """
    node_start = time.time()
    print(f"[Sentiment-Analyst] Starting...", flush=True)

    sentiment_results = []
    db: Session = SessionLocal()
    try:
        competitor_id = uuid.UUID(state["competitor_id"])

        # Pre-fetch the latest snapshot ONCE instead of per-page queries
        latest_snap = db.scalars(
            select(Snapshot)
            .where(Snapshot.competitor_id == competitor_id)
            .order_by(Snapshot.fetched_at.desc())
        ).first()

        for page in state.get("raw_pages", []):
            url = page.get("url", "")
            if ("pricing" not in url.lower()) and not page.get("is_stale") and page.get("clean_text"):
                # Call Phase 2 sentiment_score directly
                sent_res = sentiment_score(page["clean_text"])
                source_type = "review" if "review" in url.lower() or "about" in url.lower() or "docs" in url.lower() else "news"
                
                result_item = {
                    "url": url,
                    "source_type": source_type,
                    "score": sent_res["score"],
                    "topics": sent_res["topics"],
                    "sentiment_category": sent_res["sentiment_category"],
                }
                sentiment_results.append(result_item)

                # Batch — add without committing per-page
                if latest_snap:
                    ss = SentimentScore(
                        competitor_id=competitor_id,
                        snapshot_id=latest_snap.id,
                        score=sent_res["score"],
                        topics=sent_res["topics"],
                        source_type=source_type,
                        scored_at=datetime.now(timezone.utc),
                    )
                    db.add(ss)

        # Single batch commit for all sentiment scores
        db.commit()
    finally:
        db.close()

    state["sentiment_results"] = sentiment_results
    print(f"[Sentiment-Analyst] TOTAL: {time.time() - node_start:.2f}s", flush=True)
    return state


def parallel_analysis_node(state: AgentState) -> AgentState:
    """
    Parallel Analysis Node:
    Runs Change-Detector and Sentiment-Analyst concurrently using ThreadPoolExecutor.
    Both nodes write to different state keys (diffs vs sentiment_results) and use
    independent DB sessions, so concurrent execution is safe.
    """
    node_start = time.time()
    print(f"[Parallel Analysis] Starting Change-Detector + Sentiment-Analyst concurrently...", flush=True)

    with ThreadPoolExecutor(max_workers=2) as executor:
        cd_future = executor.submit(change_detector_node, state)
        sa_future = executor.submit(sentiment_analyst_node, state)

        # Wait for both — propagate any exceptions
        cd_future.result()
        sa_future.result()

    print(f"[Parallel Analysis] TOTAL: {time.time() - node_start:.2f}s", flush=True)
    return state


def report_writer_node(state: AgentState) -> AgentState:
    """
    4. Report-Writer Node:
       Synthesizes report draft using LLM provider abstraction module and saves Report row to DB.
    """
    node_start = time.time()
    print(f"[Report-Writer] Starting...", flush=True)

    pages_summary = [
        {
            "url": p.get("url"),
            "is_stale": p.get("is_stale"),
            "content_length": len(p.get("clean_text", "")),
        }
        for p in state.get("raw_pages", [])
    ]

    llm_start = time.time()
    report_md, model_used = generate_executive_report(
        competitor_name=state.get("competitor_name", "Competitor"),
        diffs=state.get("diffs", []),
        sentiment_results=state.get("sentiment_results", []),
        pages_summary=pages_summary,
        is_incomplete=state.get("is_incomplete", False),
    )
    print(f"[Report-Writer] LLM report generation: {time.time() - llm_start:.2f}s (model: {model_used})", flush=True)

    state["report_draft"] = report_md
    state["model_used"] = model_used

    db: Session = SessionLocal()
    try:
        competitor_id = uuid.UUID(state["competitor_id"])
        competitor = db.get(Competitor, competitor_id)
        user_id = competitor.user_id if competitor else None

        if user_id:
            report_row = Report(
                user_id=user_id,
                competitor_id=competitor_id,
                pdf_url=None,
                html_url=f"/reports/{competitor_id}/latest.html",
                summary=report_md[:500],
                generated_at=datetime.now(timezone.utc),
                delivered_channels=["dashboard"],
            )
            db.add(report_row)
            db.commit()
    finally:
        db.close()

    print(f"[Report-Writer] TOTAL: {time.time() - node_start:.2f}s", flush=True)
    return state
