import uuid
import time
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Any, List
from urllib.parse import urlparse

from sqlalchemy.orm import Session
from sqlalchemy import select, func

from app.database import SessionLocal
from app.models.competitor import Competitor
from app.models.snapshot import Snapshot, SourceType
from app.models.price_change import PriceChange
from app.models.sentiment_score import SentimentScore
from app.models.report import Report
from app.services.scraper import scrape_url
from app.services.diff_pricing import diff_pricing, extract_plan_prices, smart_extract_plan_prices
from app.services.sentiment import sentiment_score
from app.services.vector_store import vector_store
from app.services.llm import generate_executive_report
from app.services.agent.state import AgentState
from app.services.reports_service import send_custom_price_alert_webhook


def _detect_source_type(scrape_res: Dict[str, Any]) -> SourceType:
    """
    Determines the SourceType for a scraped page using multiple signals:
    1. URL path keywords
    2. Page title and meta description
    3. Heading content
    4. Body text signals
    Falls back to NEWS if no strong signal is detected.
    """
    url = scrape_res.get("url", "").lower()
    metadata = scrape_res.get("metadata", {})
    headings = scrape_res.get("headings", [])
    clean_text = (scrape_res.get("clean_text", "")[:2000]).lower()

    # Combine metadata text for keyword matching
    title = (metadata.get("title", "") or "").lower()
    description = (metadata.get("description", "") or "").lower()
    og_title = (metadata.get("og_title", "") or "").lower()
    heading_texts = " ".join(h.get("text", "").lower() for h in headings[:10])
    combined_meta = f"{title} {description} {og_title} {heading_texts}"

    # Pricing signals
    pricing_url_kw = any(kw in url for kw in ["pricing", "plans", "packages", "subscription", "billing", "quote", "calculator", "cost", "tier"])
    pricing_meta_kw = any(kw in combined_meta for kw in ["pricing", "plans", "per month", "per user", "free tier", "enterprise pricing", "subscription", "quote"])
    pricing_text_kw = any(kw in clean_text for kw in ["$/mo", "per month", "per user", "free plan", "pricing", "billed annually", "billed monthly", "custom pricing"])
    if pricing_url_kw or (pricing_meta_kw and pricing_text_kw):
        return SourceType.PRICING

    # Review / Product / Company signals
    review_url_kw = any(kw in url for kw in [
        "review", "about", "docs", "features", "product", "solutions", "customers",
        "testimonial", "case-stud", "enterprise", "security", "trust", "integrations", "marketplace", "compare", "vs"
    ])
    review_meta_kw = any(kw in combined_meta for kw in [
        "review", "features", "about us", "our product", "solutions", "documentation",
        "customer", "testimonial", "enterprise", "security", "integrations", "capabilities"
    ])
    if review_url_kw or review_meta_kw:
        return SourceType.REVIEW

    return SourceType.NEWS


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

        # Pass 1: Parallel seed URL scraping
        scrape_start = time.time()
        scraped_urls = set()
        raw_pages = []

        if urls:
            with ThreadPoolExecutor(max_workers=min(len(urls), 5)) as executor:
                pass1_results = list(executor.map(scrape_url, urls))
            for res in pass1_results:
                raw_pages.append(res)
                scraped_urls.add(res.get("url", "").rstrip("/"))

        print(f"[Researcher Node] Pass 1 scraping ({len(urls)} seed URLs) completed in {time.time() - scrape_start:.2f}s", flush=True)

        # Pass 2: Automatic discovery of key sub-pages (pricing, features, about, docs, reviews, news)
        discovered_urls = []
        for page in raw_pages:
            if page.get("is_stale"):
                continue
            internal_links = page.get("key_internal_links", [])
            for link_item in internal_links:
                target_url = link_item.get("url", "").rstrip("/")
                if target_url and target_url not in scraped_urls and target_url not in [u.rstrip("/") for u in discovered_urls]:
                    discovered_urls.append(link_item.get("url"))

        # Pass 2.5: Proactive pricing page probe — many competitors (e.g. OpenAI) hide pricing
        # at non-obvious URLs like /api/pricing, /chatgpt/pricing, /business/pricing.
        # Probe well-known canonical pricing paths for each unique domain.
        from app.services.scraper import generate_pricing_probe_urls

        probed_domains = set()
        for seed_url in urls:
            parsed = urlparse(seed_url)
            domain_key = f"{parsed.scheme}://{parsed.netloc}"
            if domain_key in probed_domains:
                continue
            probed_domains.add(domain_key)

            # Get homepage text for dynamic product-slug extraction
            homepage_text = ""
            for page in raw_pages:
                if page.get("url", "").rstrip("/") == seed_url.rstrip("/") and not page.get("is_stale"):
                    homepage_text = page.get("clean_text", "")
                    break

            probe_urls = generate_pricing_probe_urls(seed_url, homepage_text=homepage_text, max_probes=8)
            for probe_url in probe_urls:
                probe_clean = probe_url.rstrip("/")
                if probe_clean not in scraped_urls and probe_clean not in [u.rstrip("/") for u in discovered_urls]:
                    discovered_urls.append(probe_url)

        # Cap discovered URLs to 12 pages per run — balances complete coverage vs speed.
        # With 2 competitors: ~2-4 internal links + ~8 pricing probes per domain = fits under cap.
        discovered_urls = discovered_urls[:12]

        if discovered_urls:
            print(f"[Researcher Node] Discovered {len(discovered_urls)} key sub-page URLs: {discovered_urls}", flush=True)
            pass2_start = time.time()
            with ThreadPoolExecutor(max_workers=min(len(discovered_urls), 5)) as executor:
                pass2_results = list(executor.map(scrape_url, discovered_urls))
            for res in pass2_results:
                raw_pages.append(res)
                scraped_urls.add(res.get("url", "").rstrip("/"))
            print(f"[Researcher Node] Pass 2 sub-page scraping completed in {time.time() - pass2_start:.2f}s", flush=True)

        # Record snapshots in DB & FAISS if valid — batched commits
        db_start = time.time()
        snapshots_to_index = []
        for scrape_res in raw_pages:
            url = scrape_res.get("url", "")
            if competitor and not scrape_res["is_stale"] and scrape_res["clean_text"]:
                source_type = _detect_source_type(scrape_res)

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
    print(f"[Researcher Node] TOTAL: {time.time() - node_start:.2f}s (Analyzed {len(raw_pages)} total pages)", flush=True)
    return state


def should_reflect_edge(state: AgentState) -> str:
    """
    Conditional Reflection Edge: Pure routing function.
    If any page is_stale and retry_count < 2, loop back to Researcher node for a retry pass.
    Otherwise proceed to Change-Detector node.
    """
    has_stale = any(page.get("is_stale", False) for page in state.get("raw_pages", []))

    if has_stale and state.get("retry_count", 0) < 2:
        return "Researcher"

    return "Change-Detector"


def change_detector_node(state: AgentState) -> AgentState:
    """
    2. Change-Detector Node:
       Sets is_incomplete flag if max retries were hit with stale pages,
       and compares scraped pages using diff_pricing service.
       Persists detected price changes and baseline entries.
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
        competitor = db.get(Competitor, competitor_id)

        # Get prior pricing snapshot
        stmt = (
            select(Snapshot)
            .where(Snapshot.competitor_id == competitor_id)
            .order_by(Snapshot.fetched_at.desc())
        )
        snapshots = db.scalars(stmt).all()
        prev_text = snapshots[1].raw_content if len(snapshots) > 1 else ""

        valid_pages = [p for p in state.get("raw_pages", []) if not p.get("is_stale") and p.get("clean_text")]

        for page in valid_pages:
            clean_txt = page.get("clean_text", "")

            # 1. Detect genuine price changes vs previous snapshot
            detected_diffs = diff_pricing(prev_text, clean_txt)
            diffs.extend(detected_diffs)

            for d in detected_diffs:
                price_val = d.get("new_price") if isinstance(d.get("new_price"), (int, float)) else None
                old_val = d.get("old_price") if isinstance(d.get("old_price"), (int, float)) else None
                tier = d.get("tier_name", "General")

                pc = PriceChange(
                    competitor_id=competitor_id,
                    snapshot_before_id=snapshots[1].id if len(snapshots) > 1 else None,
                    snapshot_after_id=snapshots[0].id if len(snapshots) > 0 else None,
                    tier_name=tier,
                    old_price=old_val,
                    new_price=price_val,
                    detected_at=datetime.now(timezone.utc),
                )
                db.add(pc)

                # Trigger custom alert webhooks for detected price shifts
                user_webhook = (competitor.user.slack_webhook_url or "").strip() if competitor and competitor.user else None
                send_custom_price_alert_webhook(
                    competitor_name=competitor.name if competitor else "Competitor",
                    tier_name=tier,
                    old_price=old_val,
                    new_price=price_val,
                    user_webhook_url=user_webhook,
                )

        # 2. Extract real plan tier prices for both Competitor and User's Company
        #    Only extract from pages that are likely pricing pages (URL or content signals)
        existing_changes = db.scalar(select(func.count(PriceChange.id)).where(PriceChange.competitor_id == competitor_id)) or 0
        if existing_changes == 0 and snapshots and valid_pages:
            extracted_plans = []
            seen_tiers = set()

            user_comp_url = (competitor.company_url or "") if competitor else ""
            if competitor and competitor.user and competitor.user.company_url:
                user_comp_url = competitor.user.company_url

            # Pricing page detection keywords
            _pricing_url_kw = ("pricing", "plans", "packages", "subscription", "billing", "cost", "tier")
            _pricing_text_kw = ("$/mo", "per month", "per user", "free plan", "billed annually", "billed monthly", "per million")

            for p in valid_pages:
                page_url = p.get("url", "").lower()
                clean_text = p.get("clean_text", "")
                clean_lower = clean_text[:3000].lower()
                is_user_page = bool(user_comp_url and (user_comp_url in page_url or page_url in user_comp_url))

                # Only extract pricing from pages that are actually pricing pages
                is_pricing_page = (
                    any(kw in page_url for kw in _pricing_url_kw)
                    or any(kw in clean_lower for kw in _pricing_text_kw)
                    or is_user_page  # Always try user's own company page
                )
                if not is_pricing_page:
                    continue

                extracted = smart_extract_plan_prices(clean_text)
                for plan in extracted:
                    t_name = plan.get("tier_name", "General")
                    if is_user_page:
                        t_name = f"(Our Company) {t_name}"

                    if t_name not in seen_tiers:
                        seen_tiers.add(t_name)
                        plan["tier_name"] = t_name
                        extracted_plans.append(plan)

            for plan in extracted_plans:
                price_val = plan.get("price") if isinstance(plan.get("price"), (int, float)) else None
                baseline_pc = PriceChange(
                    competitor_id=competitor_id,
                    snapshot_before_id=None,
                    snapshot_after_id=snapshots[0].id,
                    tier_name=plan.get("tier_name", "General"),
                    old_price=None,
                    new_price=price_val,
                    detected_at=datetime.now(timezone.utc),
                )
                db.add(baseline_pc)

        db.commit()
    finally:
        db.close()

    state["diffs"] = diffs
    print(f"[Change-Detector] TOTAL: {time.time() - node_start:.2f}s", flush=True)
    return state


def sentiment_analyst_node(state: AgentState) -> AgentState:
    """
    3. Sentiment-Analyst Node:
       Analyzes scraped pages using sentiment_score service function directly.
       Persists sentiment scores to DB for Recharts visualization.
    """
    node_start = time.time()
    print(f"[Sentiment-Analyst] Starting...", flush=True)

    sentiment_results = []
    db: Session = SessionLocal()
    try:
        competitor_id = uuid.UUID(state["competitor_id"])

        latest_snap = db.scalars(
            select(Snapshot)
            .where(Snapshot.competitor_id == competitor_id)
            .order_by(Snapshot.fetched_at.desc())
        ).first()

        valid_pages = [p for p in state.get("raw_pages", []) if not p.get("is_stale") and p.get("clean_text")]

        for page in valid_pages:
            url = page.get("url", "")

            # Build enriched text: prepend metadata context for better topic extraction
            metadata = page.get("metadata", {})
            meta_prefix = ""
            meta_title = metadata.get("title") or metadata.get("og_title") or ""
            meta_desc = metadata.get("description") or metadata.get("og_description") or ""
            if meta_title:
                meta_prefix += f"{meta_title}. "
            if meta_desc:
                meta_prefix += f"{meta_desc}. "

            enriched_text = meta_prefix + page["clean_text"]
            sent_res = sentiment_score(enriched_text)

            # Use the shared source type detector for consistency
            source_type = _detect_source_type(page).value
            
            result_item = {
                "url": url,
                "source_type": source_type,
                "score": sent_res["score"],
                "topics": sent_res["topics"],
                "sentiment_category": sent_res["sentiment_category"],
            }
            sentiment_results.append(result_item)

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

    pages_summary = []
    for p in state.get("raw_pages", []):
        page_entry = {
            "url": p.get("url"),
            "is_stale": p.get("is_stale"),
            "content_length": len(p.get("clean_text", "")),
            # Include actual scraped content (capped at 3000 chars per page)
            "clean_text": p.get("clean_text", "")[:3000],
            # Include structured metadata, tables, FAQs, and tech stack for the LLM
            "metadata": p.get("metadata", {}),
            "headings": p.get("headings", [])[:20],
            "social_links": p.get("social_links", {}),
            "cta_signals": p.get("cta_signals", []),
            "markdown_tables": p.get("markdown_tables", []),
            "faqs": p.get("faqs", []),
            "tech_stack": p.get("tech_stack", []),
        }
        pages_summary.append(page_entry)

    user_company_name = "Our Company"
    user_company_url = None

    db: Session = SessionLocal()
    try:
        competitor_id = uuid.UUID(state["competitor_id"])
        competitor = db.get(Competitor, competitor_id)
        if competitor:
            user = competitor.user
            if user:
                user_company_name = user.company_name or "Our Company"
                user_company_url = user.company_url or competitor.company_url
    finally:
        db.close()

    llm_start = time.time()
    report_md, model_used = generate_executive_report(
        competitor_name=state.get("competitor_name", "Competitor"),
        diffs=state.get("diffs", []),
        sentiment_results=state.get("sentiment_results", []),
        pages_summary=pages_summary,
        is_incomplete=state.get("is_incomplete", False),
        user_company_name=user_company_name,
        user_company_url=user_company_url,
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
                summary=report_md,  # Full report markdown, not truncated
                model_used=model_used,
                generated_at=datetime.now(timezone.utc),
                delivered_channels=["dashboard"],
            )
            db.add(report_row)
            db.commit()
            db.refresh(report_row)

            # Set correct html_url using report_row.id (not competitor_id)
            report_row.html_url = f"/reports/{report_row.id}/html"
            db.commit()

            # Auto-render HTML report immediately so first click is instant
            try:
                from app.services.reports_service import render_html_report, render_pdf_report
                render_html_report(str(report_row.id), competitor.name if competitor else "Competitor", report_md)
                print(f"[Report-Writer] HTML report rendered: /reports/{report_row.id}/html", flush=True)
                render_pdf_report(str(report_row.id), competitor.name if competitor else "Competitor", report_md)
                report_row.pdf_url = f"/reports/{report_row.id}/pdf"
                db.commit()
                print(f"[Report-Writer] PDF report rendered: /reports/{report_row.id}/pdf", flush=True)
            except Exception as html_exc:
                print(f"[Report-Writer] Report render warning: {html_exc}", flush=True)

            # Index executive report into FAISS for section-aware RAG retrieval
            try:
                faiss_start = time.time()
                report_chunks_added = vector_store.add_snapshot_chunks(
                    snapshot_id=str(report_row.id),
                    competitor_id=str(competitor_id),
                    source_type="executive_report",
                    fetched_at=report_row.generated_at.isoformat(),
                    text=report_md,
                )
                print(f"[Report-Writer] FAISS indexed executive report: {report_chunks_added} section chunks in {time.time() - faiss_start:.2f}s", flush=True)
            except Exception as faiss_exc:
                print(f"[Report-Writer] FAISS indexing warning: {faiss_exc}", flush=True)
    finally:
        db.close()

    print(f"[Report-Writer] TOTAL: {time.time() - node_start:.2f}s", flush=True)
    return state
