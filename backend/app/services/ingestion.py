import uuid
from datetime import datetime, timezone
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.models.competitor import Competitor
from app.models.snapshot import Snapshot, SourceType
from app.models.price_change import PriceChange
from app.models.sentiment_score import SentimentScore
from app.services.scraper import scrape_url
from app.services.diff_pricing import diff_pricing
from app.services.sentiment import sentiment_score
from app.services.vector_store import vector_store


def ingest_url_for_competitor(
    db: Session,
    competitor: Competitor,
    source_type: SourceType,
    url: str,
    discover_subpages: bool = True,
) -> Dict[str, Any]:
    """
    Scrapes a single URL for a competitor, checks for content hash duplicates,
    creates Snapshot in Postgres, vectors in FAISS, sentiment scores, and price changes.
    If discover_subpages is True, auto-discovers and ingests key sub-pages on the same domain.
    """
    scrape_res = scrape_url(url)
    clean_text = scrape_res["clean_text"]
    content_hash = scrape_res["content_hash"]
    is_stale = scrape_res["is_stale"]
    stale_reason = scrape_res["stale_reason"]

    # Enrich clean_text with metadata context for better FAISS indexing
    metadata = scrape_res.get("metadata", {})
    meta_title = metadata.get("title") or metadata.get("og_title") or ""
    meta_desc = metadata.get("description") or metadata.get("og_description") or ""
    meta_prefix = ""
    if meta_title:
        meta_prefix += f"{meta_title}. "
    if meta_desc:
        meta_prefix += f"{meta_desc}. "
    enriched_text = (meta_prefix + clean_text) if meta_prefix else clean_text

    # Retrieve latest snapshot for this competitor and source_type
    stmt = (
        select(Snapshot)
        .where(
            Snapshot.competitor_id == competitor.id,
            Snapshot.source_type == source_type,
        )
        .order_by(Snapshot.fetched_at.desc())
    )
    latest_snapshot = db.scalars(stmt).first()

    # Skip re-ingest if content hash is identical
    if latest_snapshot and latest_snapshot.content_hash == content_hash and not is_stale:
        return {
            "status": "skipped",
            "reason": "Unchanged content hash",
            "snapshot_id": str(latest_snapshot.id),
            "is_stale": False,
            "url": url,
        }

    # Create new snapshot record — store enriched text for better retrieval
    snapshot = Snapshot(
        competitor_id=competitor.id,
        source_type=source_type,
        raw_content=enriched_text if enriched_text else scrape_res.get("raw_content", ""),
        content_hash=content_hash,
        is_stale=is_stale,
        fetched_at=datetime.now(timezone.utc),
    )
    db.add(snapshot)
    db.commit()
    db.refresh(snapshot)

    chunks_added = 0
    # Process vector embeddings if content is clean and valid
    if not is_stale and enriched_text:
        chunks_added = vector_store.add_snapshot_chunks(
            snapshot_id=str(snapshot.id),
            competitor_id=str(competitor.id),
            source_type=source_type.value,
            fetched_at=snapshot.fetched_at.isoformat(),
            text=enriched_text,
        )

        # Handle PRICING source type diffs
        if source_type == SourceType.PRICING:
            prev_text = latest_snapshot.raw_content if latest_snapshot else ""
            changes = diff_pricing(prev_text, clean_text)
            for change in changes:
                old_val = change["old_price"] if isinstance(change["old_price"], (int, float)) else None
                new_val = change["new_price"] if isinstance(change["new_price"], (int, float)) else None
                price_change = PriceChange(
                    competitor_id=competitor.id,
                    snapshot_before_id=latest_snapshot.id if latest_snapshot else None,
                    snapshot_after_id=snapshot.id,
                    tier_name=change.get("tier_name", "General"),
                    old_price=old_val,
                    new_price=new_val,
                    detected_at=datetime.now(timezone.utc),
                )
                db.add(price_change)
            db.commit()

        # Handle REVIEW & NEWS sentiment scoring
        if source_type in (SourceType.REVIEW, SourceType.NEWS):
            sent_res = sentiment_score(clean_text)
            sent_record = SentimentScore(
                competitor_id=competitor.id,
                snapshot_id=snapshot.id,
                score=sent_res["score"],
                topics=sent_res["topics"],
                source_type=source_type.value,
                scored_at=datetime.now(timezone.utc),
            )
            db.add(sent_record)
            db.commit()

    # Auto-discover and ingest key sub-pages (pricing, features, about, docs)
    subpages_ingested = 0
    if discover_subpages and not is_stale:
        internal_links = scrape_res.get("key_internal_links", [])
        for link_item in internal_links[:4]:
            target_url = link_item.get("url")
            if target_url and target_url.rstrip("/") != url.rstrip("/"):
                cat = link_item.get("category", "review")
                st = SourceType.PRICING if cat == "pricing" else (SourceType.NEWS if cat == "news" else SourceType.REVIEW)
                try:
                    ingest_url_for_competitor(db, competitor, st, target_url, discover_subpages=False)
                    subpages_ingested += 1
                except Exception as sub_exc:
                    print(f"[Ingestion] Sub-page auto-ingestion warning for {target_url}: {sub_exc}")

    return {
        "status": "ingested",
        "snapshot_id": str(snapshot.id),
        "url": url,
        "is_stale": is_stale,
        "stale_reason": stale_reason,
        "chunks_added": chunks_added,
        "content_length": len(enriched_text),
        "meta_title": meta_title,
        "meta_description": meta_desc[:200] if meta_desc else "",
        "social_links_count": len(scrape_res.get("social_links", {})),
        "headings_count": len(scrape_res.get("headings", [])),
        "cta_count": len(scrape_res.get("cta_signals", [])),
        "subpages_auto_ingested": subpages_ingested,
    }


def ingest_competitor_urls(db: Session, competitor_id: uuid.UUID) -> List[Dict[str, Any]]:
    """
    Ingests all registered URLs (pricing, review, news keywords/urls) for a given competitor.
    """
    competitor = db.get(Competitor, competitor_id)
    if not competitor:
        raise ValueError(f"Competitor with ID {competitor_id} not found")

    results = []

    # 0. Company Homepage URL (captures About, Features, etc.)
    if competitor.company_url:
        res = ingest_url_for_competitor(db, competitor, SourceType.REVIEW, competitor.company_url)
        results.append(res)

    # 1. Pricing URL
    if competitor.pricing_url:
        res = ingest_url_for_competitor(db, competitor, SourceType.PRICING, competitor.pricing_url)
        results.append(res)

    # 2. Review URLs
    if competitor.review_urls:
        for rev_url in competitor.review_urls:
            res = ingest_url_for_competitor(db, competitor, SourceType.REVIEW, rev_url)
            results.append(res)

    # 3. News URLs / Keyword Searches
    if competitor.news_keywords:
        for kw in competitor.news_keywords:
            if kw.startswith("http://") or kw.startswith("https://"):
                news_url = kw
            else:
                news_url = f"https://news.google.com/search?q={kw}&hl=en-US"
            res = ingest_url_for_competitor(db, competitor, SourceType.NEWS, news_url)
            results.append(res)

    return results
