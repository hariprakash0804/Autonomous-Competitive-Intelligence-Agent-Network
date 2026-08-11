import uuid
import time
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Any, List, Optional
from urllib.parse import urlparse

from sqlalchemy.orm import Session
from sqlalchemy import select, func

from app.database import SessionLocal
from app.models.competitor import Competitor
from app.models.snapshot import Snapshot, SourceType
from app.models.price_change import PriceChange
from app.models.sentiment_score import SentimentScore
from app.models.report import Report
from app.models.agent_run import AgentRun
from app.services.scraper import scrape_url
from app.services.diff_pricing import diff_pricing, diff_features, extract_plan_prices, smart_extract_plan_prices
from app.services.sentiment import sentiment_score
from app.services.vector_store import vector_store
from app.services.llm import generate_executive_report
from app.services.agent.state import AgentState
from app.services.reports_service import send_custom_price_alert_webhook


def _append_agent_run_log(agent_run_id_str: str, step_name: str, status: str, details: str, pages_info: list = None):
    """Persists clean execution log entries for user UI viewing."""
    if not agent_run_id_str:
        return
    db = SessionLocal()
    try:
        run = db.get(AgentRun, uuid.UUID(agent_run_id_str))
        if run:
            current_logs = list(run.execution_logs or [])
            log_entry = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "step_name": step_name,
                "status": status,
                "details": details,
            }
            current_logs.append(log_entry)
            run.execution_logs = current_logs

            if pages_info:
                current_pages = list(run.pages_visited or [])
                existing_urls = {p.get("url") for p in current_pages}
                for p in pages_info:
                    if p.get("url") and p.get("url") not in existing_urls:
                        current_pages.append(p)
                        existing_urls.add(p.get("url"))
                run.pages_visited = current_pages

            db.commit()
    except Exception as e:
        print(f"[Run Log Error] {e}")
    finally:
        db.close()



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

    # Explicit external review sites
    if any(ext in url for ext in ["trustpilot.com", "g2.com", "capterra.com", "trustradius.com"]):
        return SourceType.REVIEW

    # Pricing pages
    pricing_url_kw = any(kw in url for kw in ["pricing", "plans", "packages", "subscription", "billing", "quote", "calculator", "cost", "tier", "price", "prices", "rates", "buy", "fees", "upgrade"])
    pricing_meta_kw = any(kw in combined_meta for kw in ["pricing", "plans", "per month", "per user", "free tier", "enterprise pricing", "subscription", "quote", "rates", "buy"])
    pricing_text_kw = any(kw in clean_text for kw in ["$/mo", "per month", "per user", "free plan", "pricing", "billed annually", "billed monthly", "custom pricing", "/mo", "/month", "/year", "per seat", "starting at"])
    if pricing_url_kw or (pricing_meta_kw and pricing_text_kw):
        return SourceType.PRICING

    # External review search query URLs
    if "review" in url or "reviews" in url or "google.com/search" in url:
        return SourceType.REVIEW

    return SourceType.NEWS


def _check_cancellation(state: AgentState) -> bool:
    """Helper to check if active pipeline run has been cancelled."""
    run_id = state.get("agent_run_id")
    if not run_id:
        return False
    try:
        from app.routers.pipeline import is_run_cancelled
        return is_run_cancelled(run_id)
    except Exception:
        return False


def researcher_node(state: AgentState) -> AgentState:
    """
    1. Researcher Node:
       Increments retry_count and fetches all registered competitor URLs in parallel using ThreadPoolExecutor.
       Calls scraper.py directly for scraping and staleness evaluation.
       Uses batched DB commits and deferred FAISS saves for performance.
    """
    if _check_cancellation(state):
        print(f"[Researcher Node] Pipeline run CANCELLED. Aborting node.", flush=True)
        state["status"] = "CANCELLED"
        return state

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

        # Resolve user's own company domain so we can exclude it from competitor snapshots.
        # User company pages are still scraped for side-by-side LLM report context but should
        # NOT be stored as competitor snapshots (which would pollute change detection & sentiment).
        _user_company_domain = ""
        if competitor and competitor.user and competitor.user.company_url:
            _u_url = competitor.user.company_url.strip()
            if not _u_url.startswith(("http://", "https://")):
                _u_url = "https://" + _u_url
            _u_parsed = urlparse(_u_url)
            _user_company_domain = (_u_parsed.netloc or "").lower().split(":")[0]
            if _user_company_domain.startswith("www."):
                _user_company_domain = _user_company_domain[4:]

        # Pass 1: Parallel seed URL scraping
        scrape_start = time.time()
        scraped_urls = set()
        raw_pages = []

        if urls:
            with ThreadPoolExecutor(max_workers=min(len(urls), 10)) as executor:
                pass1_results = list(executor.map(scrape_url, urls))
            for res in pass1_results:
                raw_pages.append(res)
                scraped_urls.add(res.get("url", "").rstrip("/"))

        print(f"[Researcher Node] Pass 1 scraping ({len(urls)} seed URLs) completed in {time.time() - scrape_start:.2f}s", flush=True)

        # Pass 1.5: Lightweight fallback for failed company/pricing URLs ONLY if no valid pages were retrieved in Pass 1
        valid_pages_count = sum(1 for p in raw_pages if not p.get("is_stale") and p.get("clean_text"))
        if valid_pages_count == 0:
            _skip_domains = {"trustpilot.com", "g2.com", "google.com", "capterra.com"}
            fallback_urls = []
            for res in raw_pages:
                if res.get("is_stale") and res.get("url"):
                    _failed_url = res["url"] if res["url"].startswith(("http://", "https://")) else "https://" + res["url"]
                    parsed_failed = urlparse(_failed_url)
                    if parsed_failed.netloc and not any(sd in parsed_failed.netloc for sd in _skip_domains):
                        homepage = f"{parsed_failed.scheme or 'https'}://{parsed_failed.netloc}/"
                        if homepage.rstrip("/") not in scraped_urls:
                            fallback_urls.append(homepage)
                    if len(fallback_urls) >= 1:
                        break

            if fallback_urls:
                print(f"[Researcher Node] Fallback: trying {len(fallback_urls)} homepage(s) for failed URLs", flush=True)
                with ThreadPoolExecutor(max_workers=len(fallback_urls)) as executor:
                    fallback_results = list(executor.map(scrape_url, fallback_urls))
                for res in fallback_results:
                    if not res.get("is_stale") and res.get("clean_text"):
                        raw_pages.append(res)
                        scraped_urls.add(res.get("url", "").rstrip("/"))

        # Pass 2: Automatic discovery of sub-pages & proactive pricing probes
        # PRIORITY 1: Proactive pricing page probes (Highest priority for Competitive Intelligence)
        from app.services.scraper import generate_pricing_probe_urls

        _SKIP_PROBE_DOMAINS = {"trustpilot.com", "g2.com", "google.com", "capterra.com", "news.google.com", "trustradius.com"}

        pricing_probe_urls = []
        probed_domains = set()
        for seed_url in urls:
            _safe_seed = seed_url if seed_url.startswith(("http://", "https://")) else "https://" + seed_url
            parsed = urlparse(_safe_seed)
            if any(sd in (parsed.netloc or "").lower() for sd in _SKIP_PROBE_DOMAINS):
                continue
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

            probe_urls = generate_pricing_probe_urls(seed_url, homepage_text=homepage_text, max_probes=2)
            for probe_url in probe_urls:
                probe_clean = probe_url.rstrip("/")
                if probe_clean not in scraped_urls and probe_clean not in [u.rstrip("/") for u in pricing_probe_urls]:
                    pricing_probe_urls.append(probe_url)

        # PRIORITY 2: Key internal sub-pages (pricing, features, about, docs, reviews, news)
        general_internal_urls = []
        for page in raw_pages:
            if page.get("is_stale"):
                continue
            page_url_check = page.get("url", "").lower()
            if any(sd in page_url_check for sd in _SKIP_PROBE_DOMAINS):
                continue
            internal_links = page.get("key_internal_links", [])
            for link_item in internal_links:
                target_url = link_item.get("url", "").rstrip("/")
                if (
                    target_url
                    and target_url not in scraped_urls
                    and not any(sd in target_url.lower() for sd in _SKIP_PROBE_DOMAINS)
                    and target_url not in [u.rstrip("/") for u in pricing_probe_urls]
                    and target_url not in [u.rstrip("/") for u in general_internal_urls]
                ):
                    general_internal_urls.append(link_item.get("url"))

        # Combine: Pricing probes FIRST, then general internal links fill remaining slots (Cap: 2 max for ultra-fast execution)
        discovered_urls = (pricing_probe_urls + general_internal_urls)[:2]

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
                # Skip saving user's own company pages as competitor snapshots.
                # They are still available in raw_pages for the LLM report context.
                if _user_company_domain and _user_company_domain in url.lower():
                    print(f"[Researcher Node] Skipping snapshot for user company page: {url}", flush=True)
                    continue

                source_type = _detect_source_type(scrape_res)

                snapshot = Snapshot(
                    competitor_id=competitor.id,
                    source_type=source_type,
                    raw_content=scrape_res["clean_text"],
                    content_hash=scrape_res["content_hash"],
                    source_url=scrape_res.get("url", "")[:2048] or None,
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
    pages_info = [
        {
            "url": p.get("url"),
            "title": (p.get("metadata", {}) or {}).get("title") or (p.get("metadata", {}) or {}).get("og_title") or "Page",
            "source_type": _detect_source_type(p).value if p.get("clean_text") else "NEWS",
            "status": "Success" if not p.get("is_stale") and p.get("clean_text") else "Stale/Failed",
        }
        for p in raw_pages
    ]
    _append_agent_run_log(
        state.get("agent_run_id"),
        "Researcher Workflow Step",
        "COMPLETED",
        f"Gathered and crawled {len(raw_pages)} pages for competitor analysis.",
        pages_info=pages_info,
    )
    print(f"[Researcher Node] TOTAL: {time.time() - node_start:.2f}s (Analyzed {len(raw_pages)} total pages)", flush=True)
    return state


def should_reflect_edge(state: AgentState) -> str:
    """
    Conditional Reflection Edge: Pure routing function.
    Only reflects to Researcher if ALL scraped pages failed/stale and retry_count < 1.
    If at least one valid page was scraped, proceeds directly to Parallel-Analysis.
    """
    raw_pages = state.get("raw_pages", [])
    all_stale = all(page.get("is_stale", True) for page in raw_pages) if raw_pages else True

    if all_stale and state.get("retry_count", 0) < 1:
        return "Researcher"

    return "Parallel-Analysis"


def change_detector_node(state: AgentState) -> AgentState:
    """
    2. Change-Detector Node:
       Sets is_incomplete flag if max retries were hit with stale pages,
       and compares scraped pages using diff_pricing service.
       Persists detected price changes and baseline entries.
    """
    if _check_cancellation(state):
        print(f"[Change-Detector Node] Pipeline run CANCELLED. Aborting node.", flush=True)
        state["status"] = "CANCELLED"
        return state

    node_start = time.time()
    print(f"[Change-Detector] Starting...", flush=True)

    has_stale = any(page.get("is_stale", False) for page in state.get("raw_pages", []))
    if has_stale and state.get("retry_count", 0) >= 2:
        state["is_incomplete"] = True

    diffs = []
    feature_changes = []
    db: Session = SessionLocal()
    try:
        competitor_id = uuid.UUID(state["competitor_id"])
        competitor = db.get(Competitor, competitor_id)

        # Get current run start time to distinguish current-run snapshots from prior-run snapshots
        agent_run_id = state.get("agent_run_id")
        run_start_time = datetime.now(timezone.utc)
        if agent_run_id:
            try:
                ar = db.get(AgentRun, uuid.UUID(agent_run_id))
                if ar and ar.started_at:
                    run_start_time = ar.started_at
            except Exception:
                pass

        # Query latest snapshot created BEFORE the current pipeline run started
        prior_snapshot_stmt = (
            select(Snapshot)
            .where(
                Snapshot.competitor_id == competitor_id,
                Snapshot.fetched_at < run_start_time
            )
            .order_by(Snapshot.fetched_at.desc())
        )
        prior_snapshot = db.scalars(prior_snapshot_stmt).first()
        prev_text = prior_snapshot.raw_content if prior_snapshot else ""

        # Latest snapshot created in current run (for linking PriceChange records)
        current_snapshot_stmt = (
            select(Snapshot)
            .where(Snapshot.competitor_id == competitor_id)
            .order_by(Snapshot.fetched_at.desc())
        )
        current_snapshot = db.scalars(current_snapshot_stmt).first()

        valid_pages = [p for p in state.get("raw_pages", []) if not p.get("is_stale") and p.get("clean_text")]

        # Filter to ONLY competitor's own domain pages for change detection.
        # Exclude: external review/search sites AND the user's own company pages.
        _EXTERNAL_SEARCH_DOMAINS = {
            "trustpilot.com", "g2.com", "google.com", "capterra.com", "news.google.com",
            "trustradius.com", "producthunt.com", "gartner.com", "softwareadvice.com",
        }

        # Resolve user company domain to exclude from change detection
        _user_domain_for_cd = ""
        if competitor and competitor.user and competitor.user.company_url:
            _cd_url = competitor.user.company_url.strip()
            if not _cd_url.startswith(("http://", "https://")):
                _cd_url = "https://" + _cd_url
            _cd_parsed = urlparse(_cd_url)
            _user_domain_for_cd = (_cd_parsed.netloc or "").lower().split(":")[0]
            if _user_domain_for_cd.startswith("www."):
                _user_domain_for_cd = _user_domain_for_cd[4:]

        def _is_competitor_page(p):
            """Returns True if the page belongs to the competitor (not external review or user's company)."""
            page_url = p.get("url", "").lower()
            # Exclude external review/search domains
            if any(ext in page_url for ext in _EXTERNAL_SEARCH_DOMAINS):
                return False
            # Exclude user's own company domain
            if _user_domain_for_cd and _user_domain_for_cd in page_url:
                return False
            return True

        company_pages = [p for p in valid_pages if _is_competitor_page(p)]
        if _user_domain_for_cd:
            excluded_user_pages = len(valid_pages) - len([p for p in valid_pages if any(ext in p.get('url', '').lower() for ext in _EXTERNAL_SEARCH_DOMAINS)]) - len(company_pages)
            if excluded_user_pages > 0:
                print(f"[Change-Detector] Excluded {excluded_user_pages} user company page(s) ({_user_domain_for_cd}) from change detection.", flush=True)

        from app.services.diff_pricing import _text_similarity_ratio

        for page in company_pages:
            clean_txt = page.get("clean_text", "")
            page_hash = page.get("content_hash", "")
            page_url = page.get("url", "")

            # ── Step 1: Content-hash match (exact same content) ──────────────
            page_prior_snap = None
            if page_hash:
                hash_stmt = (
                    select(Snapshot)
                    .where(
                        Snapshot.competitor_id == competitor_id,
                        Snapshot.content_hash == page_hash,
                        Snapshot.fetched_at < run_start_time,
                    )
                    .order_by(Snapshot.fetched_at.desc())
                )
                page_prior_snap = db.scalars(hash_stmt).first()

            # If content_hash matches a prior snapshot, page is UNCHANGED — skip diffing
            if page_prior_snap:
                print(f"[Change-Detector] Content hash unchanged for {page_url}. Skipping diffing.", flush=True)
                continue

            # ── Step 2: URL-aware prior snapshot matching ────────────────────
            # Prefer prior snapshots from the SAME URL to avoid cross-page false positives
            page_prior_snap = None
            page_prev_text = ""

            if page_url:
                url_stmt = (
                    select(Snapshot)
                    .where(
                        Snapshot.competitor_id == competitor_id,
                        Snapshot.source_url == page_url,
                        Snapshot.fetched_at < run_start_time,
                    )
                    .order_by(Snapshot.fetched_at.desc())
                )
                url_prior = db.scalars(url_stmt).first()
                if url_prior:
                    page_prior_snap = url_prior
                    page_prev_text = url_prior.raw_content or ""
                    print(f"[Change-Detector] Matched prior snapshot by URL for {page_url}", flush=True)

            # ── Step 3: Best-match text similarity fallback ──────────────────
            # If no URL match (legacy snapshots without source_url), find the prior
            # snapshot with highest text overlap instead of blindly using the most recent
            if not page_prior_snap:
                fallback_stmt = (
                    select(Snapshot)
                    .where(
                        Snapshot.competitor_id == competitor_id,
                        Snapshot.fetched_at < run_start_time,
                    )
                    .order_by(Snapshot.fetched_at.desc())
                )
                prior_snaps = db.scalars(fallback_stmt).all()

                if prior_snaps:
                    # Fast path: check for exact text match
                    for ps in prior_snaps:
                        if ps.raw_content and ps.raw_content == clean_txt:
                            page_prior_snap = ps
                            page_prev_text = ps.raw_content
                            break

                    # Slow path: find best text similarity match among recent prior snapshots
                    if not page_prior_snap:
                        best_sim = 0.0
                        for ps in prior_snaps[:10]:
                            ps_text = ps.raw_content or ""
                            if not ps_text:
                                continue
                            sim = _text_similarity_ratio(ps_text, clean_txt, sample_size=8000)
                            if sim > best_sim:
                                best_sim = sim
                                page_prior_snap = ps
                                page_prev_text = ps_text
                        if page_prior_snap:
                            print(f"[Change-Detector] Best-match prior snapshot ({best_sim:.0%} similar) for {page_url}", flush=True)

            # Skip if text is identical (belt-and-suspenders with hash check above)
            if page_prev_text == clean_txt:
                print(f"[Change-Detector] Text identical for {page_url}. Skipping diffing.", flush=True)
                continue

            # ── Step 4: Similarity gate — skip if page hasn't materially changed ─
            if page_prev_text:
                sim = _text_similarity_ratio(page_prev_text, clean_txt, sample_size=8000)
                if sim >= 0.92:
                    print(f"[Change-Detector] Text {sim:.0%} similar for {page_url}. Skipping diffing.", flush=True)
                    continue

                # ── Step 5: Detect genuine pricing changes ───────────────────
                detected_diffs = diff_pricing(page_prev_text, clean_txt)
                diffs.extend(detected_diffs)

                for d in detected_diffs:
                    price_val = d.get("new_price") if isinstance(d.get("new_price"), (int, float)) else None
                    old_val = d.get("old_price") if isinstance(d.get("old_price"), (int, float)) else None
                    tier = d.get("tier_name", "General")

                    pc = PriceChange(
                        competitor_id=competitor_id,
                        snapshot_before_id=page_prior_snap.id if page_prior_snap else None,
                        snapshot_after_id=current_snapshot.id if current_snapshot else None,
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

                # ── Step 6: Detect feature changes ───────────────────────────
                detected_feature_diffs = diff_features(page_prev_text, clean_txt)
                feature_changes.extend(detected_feature_diffs)

        # 3. Extract real plan tier prices for both Competitor and User's Company
        #    Only extract from pages that are likely pricing pages (URL or content signals)
        existing_baseline_tiers = set(
            db.scalars(
                select(PriceChange.tier_name)
                .where(PriceChange.competitor_id == competitor_id, PriceChange.old_price.is_(None))
            ).all()
        )

        if current_snapshot and valid_pages:
            extracted_plans = []
            seen_tiers = set()

            # Resolve user's company domain for accurate user-page identification
            _user_domain_for_pricing = ""
            if competitor and competitor.user and competitor.user.company_url:
                _pr_url = competitor.user.company_url.strip()
                if not _pr_url.startswith(("http://", "https://")):
                    _pr_url = "https://" + _pr_url
                _pr_parsed = urlparse(_pr_url)
                _user_domain_for_pricing = (_pr_parsed.netloc or "").lower().split(":")[0]
                if _user_domain_for_pricing.startswith("www."):
                    _user_domain_for_pricing = _user_domain_for_pricing[4:]

            # Pricing page detection keywords
            _pricing_url_kw = ("pricing", "plans", "packages", "subscription", "billing", "cost", "tier", "price", "prices", "rates", "buy", "fees", "upgrade")
            _pricing_text_kw = ("$/mo", "per month", "per user", "free plan", "billed annually", "billed monthly", "per million", "/mo", "/month", "/year", "per seat", "starting at", "contact sales", "get quote", "custom pricing")

            for p in valid_pages:
                page_url = p.get("url", "").lower()
                clean_text = p.get("clean_text", "")
                clean_lower = clean_text[:3000].lower()
                # Domain-based detection: check if the page's domain matches the user's company domain
                is_user_page = bool(_user_domain_for_pricing and _user_domain_for_pricing in page_url)

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

                    if t_name not in seen_tiers and t_name not in existing_baseline_tiers:
                        seen_tiers.add(t_name)
                        plan["tier_name"] = t_name
                        extracted_plans.append(plan)

            for plan in extracted_plans:
                price_val = plan.get("price") if isinstance(plan.get("price"), (int, float)) else None
                baseline_pc = PriceChange(
                    competitor_id=competitor_id,
                    snapshot_before_id=None,
                    snapshot_after_id=current_snapshot.id,
                    tier_name=plan.get("tier_name", "General"),
                    old_price=None,
                    new_price=price_val,
                    detected_at=datetime.now(timezone.utc),
                )
                db.add(baseline_pc)

        db.commit()
    finally:
        db.close()

    # Filter: Only count GENUINE pricing changes (old_price -> new_price) as diffs.
    # Baseline detections (old_price is None = first-time price discovery) are already
    # persisted to DB for price history, but should NOT trigger LLM report generation.
    genuine_price_diffs = [d for d in diffs if d.get("old_price") is not None]

    state["diffs"] = genuine_price_diffs
    state["feature_diffs"] = feature_changes

    # Build log message
    has_changes = bool(genuine_price_diffs or feature_changes)
    log_parts = []
    if genuine_price_diffs:
        log_parts.append(f"{len(genuine_price_diffs)} pricing change(s)")
    if feature_changes:
        log_parts.append(f"{len(feature_changes)} feature change(s)")

    if has_changes:
        log_detail = f"Detected {', '.join(log_parts)} across monitored pages."
    else:
        log_detail = "No changes in pricing or features detected for the competitor."

    _append_agent_run_log(
        state.get("agent_run_id"),
        "Change & Pricing Detector Workflow Step",
        "COMPLETED",
        log_detail,
    )
    print(f"[Change-Detector] TOTAL: {time.time() - node_start:.2f}s ({log_detail})", flush=True)
    return state


def sentiment_analyst_node(state: AgentState) -> AgentState:
    """
    3. Sentiment-Analyst Node:
       Analyzes scraped pages using sentiment_score service function directly.
       Persists sentiment scores to DB for Recharts visualization.
    """
    if _check_cancellation(state):
        print(f"[Sentiment-Analyst Node] Pipeline run CANCELLED. Aborting node.", flush=True)
        state["status"] = "CANCELLED"
        return state

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

        # Resolve the user's own company domain to exclude from competitor sentiment analysis.
        # The user's own company pages (e.g., openai.com/pricing) are scraped for side-by-side
        # comparison but should NOT bias the competitor's sentiment score.
        user_company_domain = ""
        competitor_obj = db.get(Competitor, competitor_id)
        if competitor_obj and competitor_obj.user:
            user_url = (competitor_obj.user.company_url or "").strip()
            if user_url:
                if not user_url.startswith(("http://", "https://")):
                    user_url = "https://" + user_url
                parsed_user = urlparse(user_url)
                user_company_domain = (parsed_user.netloc or "").lower().split(":")[0]
                if user_company_domain.startswith("www."):
                    user_company_domain = user_company_domain[4:]

        valid_pages = [p for p in state.get("raw_pages", []) if not p.get("is_stale") and p.get("clean_text")]

        # Google Search/News pages return boilerplate UI text (cookie dialogs, "About X results",
        # bot-detection messages, navigation noise) that VADER interprets as negative sentiment.
        # These pages are excluded from sentiment scoring but remain in raw_pages for the
        # LLM Report Writer to use as context (e.g., discovering trending news headlines).
        _SENTIMENT_EXCLUDE_DOMAINS = {"google.com/search", "news.google.com"}

        def _is_google_boilerplate(page_url: str) -> bool:
            """Returns True if the URL is a Google search/news result page with boilerplate text."""
            url_lower = page_url.lower()
            return any(domain in url_lower for domain in _SENTIMENT_EXCLUDE_DOMAINS)

        google_excluded = [p for p in valid_pages if _is_google_boilerplate(p.get("url", ""))]
        if google_excluded:
            print(f"[Sentiment-Analyst] Excluded {len(google_excluded)} Google search/news boilerplate page(s) from sentiment analysis: {[p.get('url', '') for p in google_excluded]}", flush=True)
        valid_pages_filtered = [p for p in valid_pages if not _is_google_boilerplate(p.get("url", ""))]

        # Filter out the user's own company pages from sentiment analysis to avoid bias.
        # The user's marketing content is naturally positive and dilutes competitor sentiment.
        if user_company_domain:
            competitor_pages = [
                p for p in valid_pages_filtered
                if user_company_domain not in (p.get("url", "").lower())
            ]
            skipped_count = len(valid_pages_filtered) - len(competitor_pages)
            if skipped_count > 0:
                print(f"[Sentiment-Analyst] Excluded {skipped_count} user company page(s) ({user_company_domain}) from competitor sentiment analysis.", flush=True)
        else:
            competitor_pages = valid_pages_filtered

        for page in competitor_pages:
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

            # Use the shared source type detector for consistency
            source_type = _detect_source_type(page).value

            # For review pages (Trustpilot, G2, Google search reviews), use larger text
            # sample to capture more review content and reduce marketing boilerplate dilution
            page_text = page["clean_text"]
            if source_type == "review":
                enriched_text = meta_prefix + page_text[:8000]
            else:
                enriched_text = meta_prefix + page_text

            sent_res = sentiment_score(enriched_text)

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

        # Separately calculate User Company sentiment for dual-company comparative analysis
        # Also exclude Google boilerplate pages from user company sentiment to prevent the same bias
        user_company_pages = [
            p for p in valid_pages
            if user_company_domain
            and user_company_domain in p.get("url", "").lower()
            and not _is_google_boilerplate(p.get("url", ""))
        ]
        user_sentiment_results = []
        for page in user_company_pages:
            url = page.get("url", "")
            metadata = page.get("metadata", {})
            meta_prefix = ""
            meta_title = metadata.get("title") or metadata.get("og_title") or ""
            meta_desc = metadata.get("description") or metadata.get("og_description") or ""
            if meta_title:
                meta_prefix += f"{meta_title}. "
            if meta_desc:
                meta_prefix += f"{meta_desc}. "
            source_type = _detect_source_type(page).value
            enriched_text = meta_prefix + page["clean_text"][:8000]
            sent_res = sentiment_score(enriched_text)
            user_sentiment_results.append({
                "url": url,
                "source_type": source_type,
                "score": sent_res["score"],
                "topics": sent_res["topics"],
                "sentiment_category": sent_res["sentiment_category"],
                "is_user_company": True,
            })

        # Fallback: if user didn't provide a company URL, analyze user's onboarded document/text synthesis
        if not user_sentiment_results and competitor_obj and competitor_obj.user and competitor_obj.user.company_description:
            user_desc = competitor_obj.user.company_description
            sent_res = sentiment_score(user_desc)
            user_sentiment_results.append({
                "url": "Onboarded Document/Text Profile",
                "source_type": "NEWS",
                "score": sent_res["score"],
                "topics": sent_res["topics"],
                "sentiment_category": sent_res["sentiment_category"],
                "is_user_company": True,
            })

        db.commit()
    finally:
        db.close()

    state["sentiment_results"] = sentiment_results
    state["user_sentiment_results"] = user_sentiment_results
    _append_agent_run_log(
        state.get("agent_run_id"),
        "Sentiment Analyst Workflow Step",
        "COMPLETED",
        f"Analyzed customer sentiment across {len(sentiment_results)} competitor pages.",
    )
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


def _format_gmt_datetime(dt: Optional[datetime], fmt: str = "%b %d, %Y %I:%M %p GMT") -> str:
    if not dt:
        return "Unknown"
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.strftime(fmt)


def report_writer_node(state: AgentState) -> AgentState:
    """
    4. Report-Writer Node:
       Synthesizes report draft using LLM provider abstraction module and saves Report row to DB.
       Skips LLM report generation if no pricing or feature changes were detected.
    """
    if _check_cancellation(state):
        print(f"[Report-Writer Node] Pipeline run CANCELLED. Aborting node.", flush=True)
        state["status"] = "CANCELLED"
        return state

    node_start = time.time()
    print(f"[Report-Writer] Starting...", flush=True)

    diffs = state.get("diffs", [])
    feature_diffs = state.get("feature_diffs", [])
    has_any_changes = bool(diffs or feature_diffs)

    db: Session = SessionLocal()
    has_prior_real_report = False
    prior_report_summary = ""
    prior_report_date = ""
    prior_report_model = ""
    try:
        competitor_id = uuid.UUID(state["competitor_id"])
        existing_real_report = db.scalars(
            select(Report)
            .where(
                Report.competitor_id == competitor_id,
                Report.model_used != "skipped (no changes)",
                Report.model_used != "reused (no changes)",
            )
            .order_by(Report.generated_at.desc())
        ).first()
        if existing_real_report:
            has_prior_real_report = True
            prior_report_summary = existing_real_report.summary or ""
            prior_report_date = _format_gmt_datetime(existing_real_report.generated_at)
            prior_report_model = existing_real_report.model_used or "unknown"
    finally:
        db.close()

    # ── Reuse previous report if a prior real report exists AND no new pricing/feature changes were detected ──
    if has_prior_real_report and not has_any_changes:
        print(f"[Report-Writer] Prior report exists and no new changes detected. Reusing previous detailed report.", flush=True)

        # Build the banner + previous report content
        no_change_banner = (
            f"> ⚠️ **Previous Pipeline Data**: No new pricing or feature changes were detected in this scan. "
            f"The report below is from the most recent analysis run ({prior_report_date}).\n\n"
            f"---\n\n"
        )

        # Use the full previous report content with the banner prepended
        reused_summary = no_change_banner + prior_report_summary

        state["report_draft"] = reused_summary
        state["model_used"] = "reused (no changes)"

        # Save a record so the user has a history of pipeline runs with the full report
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
                    summary=reused_summary,
                    model_used="reused (no changes)",
                    generated_at=datetime.now(timezone.utc),
                    delivered_channels=["dashboard"],
                )
                db.add(report_row)
                db.commit()
                db.refresh(report_row)
                report_row.html_url = f"/reports/{report_row.id}/html"
                db.commit()

                # Also render HTML/PDF so the report is viewable immediately
                try:
                    from app.services.reports_service import render_html_report, render_pdf_report
                    comp_name = competitor.name if competitor else "Competitor"
                    r_id_str = str(report_row.id)
                    with ThreadPoolExecutor(max_workers=2) as render_pool:
                        h_fut = render_pool.submit(render_html_report, r_id_str, comp_name, reused_summary)
                        p_fut = render_pool.submit(render_pdf_report, r_id_str, comp_name, reused_summary)
                        h_fut.result()
                        p_fut.result()
                    report_row.pdf_url = f"/reports/{report_row.id}/pdf"
                    db.commit()
                    print(f"[Report-Writer] HTML & PDF rendered for reused report {report_row.id}", flush=True)
                except Exception as render_exc:
                    print(f"[Report-Writer] Reused report render warning: {render_exc}", flush=True)
        finally:
            db.close()

        _append_agent_run_log(
            state.get("agent_run_id"),
            "Report Writer Workflow Step",
            "COMPLETED",
            f"No new changes detected — showing previous detailed report from {prior_report_date}.",
        )
        print(f"[Report-Writer] TOTAL: {time.time() - node_start:.2f}s (reused previous report)", flush=True)
        return state

    # ── Full report generation when changes ARE detected ──
    # Build change summary for the LLM context
    change_parts = []
    if diffs:
        change_parts.append(f"PRICING CHANGES ({len(diffs)}):")
        for d in diffs:
            change_parts.append(f"  - {d.get('details', str(d))}")
    if feature_diffs:
        change_parts.append(f"\nFEATURE CHANGES ({len(feature_diffs)}):")
        for fd in feature_diffs:
            change_parts.append(f"  - {fd.get('details', str(fd))}")

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
    user_company_description = None

    db: Session = SessionLocal()
    try:
        competitor_id = uuid.UUID(state["competitor_id"])
        competitor = db.get(Competitor, competitor_id)
        if competitor and competitor.user:
            user = competitor.user
            user_company_name = user.company_name or "Our Company"
            user_company_url = user.company_url
            user_company_description = user.company_description
    finally:
        db.close()

    # Retrieve user feedback reflection exemplars (RLHF) from vector store
    feedback_exemplars = []
    try:
        from app.services.vector_store import vector_store
        fb_docs = vector_store.similarity_search("user_feedback_exemplar", k=3)
        for doc in fb_docs:
            if doc:
                text = getattr(doc, "page_content", "") or (doc.get("chunk_text") if isinstance(doc, dict) else "")
                if text:
                    feedback_exemplars.append(text[:600])
        if feedback_exemplars:
            print(f"[Report-Writer Node] Retained {len(feedback_exemplars)} user feedback exemplars for reflection tuning.", flush=True)
    except Exception as e_fb:
        print(f"[Report-Writer Node] Feedback memory query notice: {e_fb}", flush=True)

    # Combine pricing diffs + feature diffs for the LLM
    combined_diffs = list(diffs)
    for fd in feature_diffs:
        combined_diffs.append({
            "tier_name": f"[Feature] {fd.get('change_type', 'change')}",
            "old_price": fd.get("change_type"),
            "new_price": fd.get("feature"),
            "details": fd.get("details", ""),
        })

    llm_start = time.time()
    report_md, model_used = generate_executive_report(
        competitor_name=state.get("competitor_name", "Competitor"),
        diffs=combined_diffs,
        sentiment_results=state.get("sentiment_results", []),
        pages_summary=pages_summary,
        is_incomplete=state.get("is_incomplete", False),
        user_company_name=user_company_name,
        user_company_url=user_company_url,
        user_company_description=user_company_description,
        user_feedback_exemplars=feedback_exemplars if feedback_exemplars else None,
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

            # Auto-render HTML and PDF reports concurrently so response is instant
            try:
                from app.services.reports_service import render_html_report, render_pdf_report
                comp_name = competitor.name if competitor else "Competitor"
                r_id_str = str(report_row.id)

                with ThreadPoolExecutor(max_workers=2) as render_pool:
                    h_fut = render_pool.submit(render_html_report, r_id_str, comp_name, report_md)
                    p_fut = render_pool.submit(render_pdf_report, r_id_str, comp_name, report_md)
                    h_fut.result()
                    p_fut.result()

                report_row.pdf_url = f"/reports/{report_row.id}/pdf"
                db.commit()
                print(f"[Report-Writer] HTML & PDF reports rendered concurrently for report {report_row.id}", flush=True)
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

    _append_agent_run_log(
        state.get("agent_run_id"),
        "Executive Report Synthesis Workflow Step",
        "COMPLETED",
        f"Generated executive report via {model_used}. Report saved & ready.",
    )
    print(f"[Report-Writer] TOTAL: {time.time() - node_start:.2f}s", flush=True)
    return state
