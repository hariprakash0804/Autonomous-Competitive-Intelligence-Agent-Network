import uuid
from datetime import datetime, timezone
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
       Increments retry_count and fetches all registered competitor URLs.
       Calls scraper.py directly for scraping and staleness evaluation.
    """
    if state.get("retry_count", 0) >= 1:
        state["reflection_triggered"] = True

    state["retry_count"] = state.get("retry_count", 0) + 1
    raw_pages = []

    db: Session = SessionLocal()
    try:
        competitor_id = uuid.UUID(state["competitor_id"])
        competitor = db.get(Competitor, competitor_id)
        if competitor:
            state["competitor_name"] = competitor.name

        for url in state["urls"]:
            # Directly call Phase 2 scraper service function
            scrape_res = scrape_url(url)
            raw_pages.append(scrape_res)

            # Record snapshot in DB & FAISS if valid
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
                db.commit()
                db.refresh(snapshot)

                vector_store.add_snapshot_chunks(
                    snapshot_id=str(snapshot.id),
                    competitor_id=str(competitor.id),
                    source_type=source_type.value,
                    fetched_at=snapshot.fetched_at.isoformat(),
                    text=scrape_res["clean_text"],
                )
    finally:
        db.close()

    state["raw_pages"] = raw_pages
    return state


def should_reflect_edge(state: AgentState) -> str:
    """
    Conditional Reflection Edge:
    If any page is_stale and retry_count < 2, loop back to Researcher node.
    Otherwise proceed to Change-Detector node.
    """
    has_stale = any(page.get("is_stale", False) for page in state.get("raw_pages", []))

    if has_stale and state["retry_count"] < 2:
        return "Researcher"

    if has_stale and state["retry_count"] >= 2:
        state["is_incomplete"] = True

    return "Change-Detector"


def change_detector_node(state: AgentState) -> AgentState:
    """
    2. Change-Detector Node:
       Compares pricing pages using Phase 2 diff_pricing service function directly.
    """
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
    return state


def sentiment_analyst_node(state: AgentState) -> AgentState:
    """
    3. Sentiment-Analyst Node:
       Analyzes review and news pages using Phase 2 sentiment_score service function directly.
    """
    sentiment_results = []
    db: Session = SessionLocal()
    try:
        competitor_id = uuid.UUID(state["competitor_id"])

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

                # Fetch snapshot for this url if available
                snap = db.scalars(
                    select(Snapshot)
                    .where(Snapshot.competitor_id == competitor_id)
                    .order_by(Snapshot.fetched_at.desc())
                ).first()

                if snap:
                    ss = SentimentScore(
                        competitor_id=competitor_id,
                        snapshot_id=snap.id,
                        score=sent_res["score"],
                        topics=sent_res["topics"],
                        source_type=source_type,
                        scored_at=datetime.now(timezone.utc),
                    )
                    db.add(ss)
                db.commit()
    finally:
        db.close()

    state["sentiment_results"] = sentiment_results
    return state


def report_writer_node(state: AgentState) -> AgentState:
    """
    4. Report-Writer Node:
       Synthesizes report draft using LLM provider abstraction module and saves Report row to DB.
    """
    pages_summary = [
        {
            "url": p.get("url"),
            "is_stale": p.get("is_stale"),
            "content_length": len(p.get("clean_text", "")),
        }
        for p in state.get("raw_pages", [])
    ]

    report_md, model_used = generate_executive_report(
        competitor_name=state.get("competitor_name", "Competitor"),
        diffs=state.get("diffs", []),
        sentiment_results=state.get("sentiment_results", []),
        pages_summary=pages_summary,
        is_incomplete=state.get("is_incomplete", False),
    )

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

    return state
