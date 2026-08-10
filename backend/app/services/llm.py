import os
import time
from typing import Dict, Any, Tuple, List, Optional
import traceback
from openai import OpenAI, RateLimitError, APIError

from app.config import settings

# Primary and Fallback active OpenRouter free models
PRIMARY_FREE_MODEL = "google/gemma-2-9b-it:free"
FALLBACK_FREE_MODEL = "meta-llama/llama-3.1-8b-instruct:free"
ALTERNATIVE_FREE_MODEL = "mistralai/mistral-7b-instruct:free"

# Proactive rate-limiting: minimum delay between LLM requests
MIN_REQUEST_INTERVAL_SECONDS = 0.5
_last_request_timestamp = 0.0

# Cached OpenAI client to avoid repeated TLS handshake overhead
_cached_client: Optional[OpenAI] = None
_cached_client_key: str = ""


def _enforce_proactive_rate_limit():
    """Proactively ensures at least 0.5s between LLM calls to respect 20 req/min limit."""
    global _last_request_timestamp
    elapsed = time.time() - _last_request_timestamp
    if elapsed < MIN_REQUEST_INTERVAL_SECONDS:
        wait_time = MIN_REQUEST_INTERVAL_SECONDS - elapsed
        print(f"[OpenRouter Rate Limit Guard] Waiting {wait_time:.2f}s to respect 20 req/min limit...")
        time.sleep(wait_time)
    _last_request_timestamp = time.time()


def _get_cached_client(api_key: str) -> OpenAI:
    """Returns a cached OpenAI client to avoid repeated TLS handshake overhead."""
    global _cached_client, _cached_client_key
    if _cached_client is None or _cached_client_key != api_key:
        _cached_client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key,
            default_headers={
                "HTTP-Referer": "https://github.com/Autonomous-Competitive-Intelligence-Agent-Network",
                "X-Title": "Autonomous Competitive Intelligence Agent Network",
            },
        )
        _cached_client_key = api_key
    return _cached_client


def _repair_truncated_markdown(text: str) -> str:
    """
    Auto-repairs Markdown output that was truncated due to LLM max_tokens cutoff.
    Fixes incomplete table rows, unclosed code blocks, and cut-off headers/lines.
    """
    if not text:
        return ""

    cleaned = text.strip()

    # 1. Fix unclosed fenced code blocks ```
    code_block_count = cleaned.count("```")
    if code_block_count % 2 != 0:
        cleaned += "\n```"

    # 2. Fix incomplete table row at the end if truncated mid-line
    lines = cleaned.split("\n")
    if lines:
        last_line = lines[-1].strip()
        # If last line starts with '|' or contains multiple '|' columns but doesn't end with '|'
        if last_line.startswith("|") or (last_line.count("|") >= 2 and not last_line.endswith("|")):
            if not last_line.endswith("|"):
                lines[-1] = last_line + " |"
            cleaned = "\n".join(lines)

    return cleaned


def call_openrouter(prompt: str, api_key: str, max_tokens: int = 6000) -> Tuple[str, str]:
    """
    Invokes OpenRouter API using OpenAI SDK with active free models pool.
    Proactively enforces a 0.5s delay and reactively catches 429 rate limits
    or API errors to automatically try fallbacks. Auto-repairs truncated outputs.
    Returns (response_text, actual_model_served).
    """
    client = _get_cached_client(api_key)

    models_to_try = [
        "openrouter/free",
    ]
    
    last_exception = None

    for idx, model in enumerate(models_to_try):
        # 1. Proactive Rate Limit Delay
        _enforce_proactive_rate_limit()

        try:
            print(f"[OpenRouter Request] Attempting model '{model}' with 45s HTTP timeout guard (max_tokens={max_tokens})...")
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=max_tokens,
                timeout=45.0,
            )
            model_served = getattr(response, "model", model)
            finish_reason = getattr(response.choices[0], "finish_reason", "")
            content = response.choices[0].message.content or ""
            
            if finish_reason == "length":
                print("[OpenRouter Warning] Response reached max_tokens limit. Auto-repairing truncated markdown structure...", flush=True)

            repaired_content = _repair_truncated_markdown(content)
            return repaired_content, str(model_served)

        except Exception as exc:
            last_exception = exc
            err_msg = str(exc)
            
            # Fast-fail if account daily quota is exceeded (no free model will work until reset/credits added)
            if "free-models-per-day" in err_msg.lower() or "daily limit" in err_msg.lower():
                print(f"[OpenRouter Daily Limit] Daily free request quota exceeded. Fast-failing to regex/rule fallbacks.", flush=True)
                raise exc

            is_429 = isinstance(exc, RateLimitError) or "429" in err_msg or "rate limit" in err_msg.lower()
            is_404 = getattr(exc, "status_code", None) == 404 or "404" in err_msg or "unavailable for free" in err_msg.lower()

            if is_429:
                print(f"[OpenRouter 429 Rate Limit] Model '{model}' rate-limited. Retrying next candidate in 1s...")
                time.sleep(1.0)
            elif is_404:
                print(f"[OpenRouter 404 Deprecated/Paid] Model '{model}' unavailable for free. Trying fallback candidate...")
            else:
                print(f"[OpenRouter Error/Timeout] Model '{model}' failed: {exc}. Retrying next candidate...")

    raise last_exception if last_exception else RuntimeError("All OpenRouter candidate models failed.")


def _build_rich_context(pages_summary: list[dict], user_company_name: str, user_company_url: Optional[str]) -> str:
    """
    Builds a rich structured context string from scraped pages for the LLM prompt.
    Extracts and formats: metadata, headings, content snippets, social links, CTA signals.
    """
    sections = []
    for idx, p in enumerate(pages_summary, 1):
        if p.get("is_stale"):
            continue

        url = p.get("url", "Unknown")
        metadata = p.get("metadata", {})
        headings = p.get("headings", [])
        social = p.get("social_links", {})
        ctas = p.get("cta_signals", [])
        content = p.get("clean_text", "")

        # Determine if this is the user's own company page
        is_user_page = bool(user_company_url and (
            user_company_url.rstrip("/") in url or url in user_company_url
        ))
        label = f"[YOUR COMPANY PAGE]" if is_user_page else "[COMPETITOR PAGE]"

        page_ctx = f"--- Page {idx} {label}: {url} ---\n"

        # Metadata
        title = metadata.get("title") or metadata.get("og_title") or ""
        description = metadata.get("description") or metadata.get("og_description") or ""
        site_name = metadata.get("og_site_name") or ""
        if title:
            page_ctx += f"Title: {title}\n"
        if site_name:
            page_ctx += f"Site Name: {site_name}\n"
        if description:
            page_ctx += f"Description: {description}\n"
        keywords = metadata.get("keywords", [])
        if keywords:
            page_ctx += f"Keywords: {', '.join(keywords[:15])}\n"

        # JSON-LD highlights
        jsonld_items = metadata.get("jsonld", [])
        for ld in jsonld_items[:3]:
            ld_type = ld.get("@type", "")
            if ld_type:
                page_ctx += f"Schema.org Type: {ld_type}\n"
            ld_desc = ld.get("description", "")
            if ld_desc and len(ld_desc) > 10:
                page_ctx += f"Schema Description: {ld_desc[:300]}\n"
            ld_name = ld.get("name", "")
            if ld_name:
                page_ctx += f"Schema Name: {ld_name}\n"

        # Headings hierarchy (captures feature sections, product areas)
        if headings:
            heading_strs = [f"{'#' * h['level']} {h['text']}" for h in headings[:15]]
            page_ctx += f"Page Structure (Headings):\n" + "\n".join(heading_strs) + "\n"

        # Social presence
        if social:
            social_strs = [f"{k}: {v}" for k, v in social.items()]
            page_ctx += f"Social/Contact: {' | '.join(social_strs)}\n"

        # Technographics / Tech Stack
        tech_stack = p.get("tech_stack", [])
        if tech_stack:
            page_ctx += f"Detected Tech Stack: {', '.join(tech_stack)}\n"

        # CTA signals
        if ctas:
            page_ctx += f"Call-to-Action Signals: {' | '.join(ctas[:10])}\n"

        # Markdown Tables (Pricing matrices, Feature comparison tables)
        tables = p.get("markdown_tables", [])
        if tables:
            page_ctx += f"Scraped Comparison/Pricing Tables:\n" + "\n\n".join(tables[:3]) + "\n"

        # FAQs
        faqs = p.get("faqs", [])
        if faqs:
            faq_strs = [f"Q: {f.get('question')}\nA: {f.get('answer')}" for f in faqs[:5]]
            page_ctx += f"Extracted FAQs:\n" + "\n\n".join(faq_strs) + "\n"

        # Actual page content (first 2500 chars)
        if content:
            page_ctx += f"Page Content:\n{content[:2500]}\n"

        sections.append(page_ctx)

    return "\n\n".join(sections) if sections else "No valid page content was extracted."


def generate_executive_report(
    competitor_name: str,
    diffs: list[dict],
    sentiment_results: list[dict],
    pages_summary: list[dict],
    is_incomplete: bool = False,
    user_company_name: str = "Our Company",
    user_company_url: Optional[str] = None,
    user_feedback_exemplars: Optional[List[str]] = None,
) -> Tuple[str, str]:
    """
    Generates a structured comparative competitive intelligence report.
    Uses rich scraped content (metadata, headings, CTAs, actual text) to produce
    data-driven analysis. Includes Features, Pricing, Advantages, and Disadvantages.
    Incorporates user feedback exemplars (RLHF) to tune report reflection.
    Returns (report_markdown, model_info_string).
    """
    provider = (settings.LLM_PROVIDER or "").lower().strip()
    api_key = settings.LLM_API_KEY or ""

    # Build rich context from all scraped pages
    rich_context = _build_rich_context(pages_summary, user_company_name, user_company_url)

    feedback_context = ""
    if user_feedback_exemplars:
        feedback_context = f"\n═══════════════════════════════════════════════\nUSER FEEDBACK & REFLECTION LEARNING EXEMPLARS (RLHF Memory)\n═══════════════════════════════════════════════\n" + "\n---\n".join(user_feedback_exemplars) + "\n"

    prompt = f"""
You are an expert Competitive Intelligence Analyst. Generate a comprehensive, data-driven comparative intelligence report comparing '{user_company_name}' vs '{competitor_name}'.

IMPORTANT RULES:
- Base your analysis STRICTLY on the scraped page data provided below. Do NOT fabricate features, prices, or capabilities.
- Write out full details, tables, and bullet points. Do NOT abbreviate or skip sections.

═══════════════════════════════════════════════
SCRAPED PAGE DATA (Primary Source)
═══════════════════════════════════════════════
{rich_context}
{feedback_context}
═══════════════════════════════════════════════
PRICING CHANGES & TIERS DETECTED
═══════════════════════════════════════════════
{diffs if diffs else "No pricing tier changes detected. no new features applied in the competitor company."}

═══════════════════════════════════════════════
SENTIMENT & TOPIC ANALYSIS
═══════════════════════════════════════════════
{sentiment_results if sentiment_results else "No sentiment data available."}

═══════════════════════════════════════════════

Your report MUST include ALL 6 sections completely without stopping mid-section:

# Competitive Intelligence Executive Summary: {user_company_name} vs {competitor_name}

## Executive Brief
Detailed comparative summary comparing positioning, target audience, key technology, and strategic focus based on the scraped content.

## 1. Feature & Capability Comparison Matrix
Compare product capabilities, developer tools, model offerings, security, and integrations. Use a complete Markdown table with dimensions: Core Product, Key Features, Target Audience, Technology, and Integrations.

## 2. Pricing & Tier Structure Comparison
Provide a thorough breakdown of ALL pricing plans, subscription tiers, per-token rates, and enterprise pricing from the scraped data. Quote exact prices (e.g. Free, $20/user/mo, $25/user/mo, per-token rates like $0.075/M input tokens, $0.30/M output tokens, $0.59/M input, $0.79/M output). Detail what each tier includes.

## 3. Key Advantages of {user_company_name} over {competitor_name}
Detailed bulleted list of strengths, capabilities, and features where {user_company_name} leads based on the scraped data.

## 4. Key Disadvantages & Gaps of {user_company_name} vs {competitor_name}
Detailed bulleted list of areas where {competitor_name} holds an advantage (e.g., lower token cost, faster speed, open models, specialized custom silicon, unique integrations).

## 5. Sentiment & Market Perception Analysis
Summarize sentiment scores, market perception, and top topics extracted from the ingested content.

## 6. Strategic Recommendations & Action Plan
Provide 3-4 concrete, actionable strategic recommendations for product roadmap, pricing positioning, and competitive differentiation.

CRITICAL: Output ALL 6 sections completely. Do NOT stop mid-section or truncate.
"""

    if is_incomplete:
        prompt += "\nNOTE: Highlight that some page scrapes were flagged stale after maximum retries."

    # 1. OpenRouter Provider Execution
    if provider == "openrouter" and api_key:
        try:
            report_text, model_used = call_openrouter(prompt, api_key, max_tokens=10000)
            return report_text, f"openrouter/{model_used}"
        except Exception as exc:
            print(f"[OpenRouter API Failure] {exc}. Falling back to instant structured comparative generator.")

    # 2. Keyless Fallback — Data-Driven Structured Report Generator
    # Extract real information from scraped pages instead of using generic placeholders
    stale_notice = (
        "> [!WARNING]\n> **Data Collection Incomplete**: One or more source pages were flagged stale after retries.\n\n"
        if is_incomplete
        else ""
    )

    # ── Build company profiles from extracted metadata ────────────────────
    user_profile = {"title": user_company_name, "description": "", "headings": [], "ctas": [], "social": {}}
    competitor_profile = {"title": competitor_name, "description": "", "headings": [], "ctas": [], "social": {}}

    for p in pages_summary:
        if p.get("is_stale"):
            continue
        url = p.get("url", "")
        metadata = p.get("metadata", {})
        is_user_page = bool(user_company_url and (
            user_company_url.rstrip("/") in url or url in user_company_url
        ))
        target = user_profile if is_user_page else competitor_profile

        # Take the best description available
        desc = metadata.get("description") or metadata.get("og_description") or ""
        if desc and (not target["description"] or len(desc) > len(target["description"])):
            target["description"] = desc

        title = metadata.get("title") or metadata.get("og_title") or ""
        if title and (not target["title"] or target["title"] in (user_company_name, competitor_name)):
            target["title"] = title

        target["headings"].extend(p.get("headings", []))
        target["ctas"].extend(p.get("cta_signals", []))
        target["social"].update(p.get("social_links", {}))

    # ── Build feature comparison from headings ────────────────────────────
    def _extract_feature_bullets(profile: dict, name: str) -> str:
        bullets = []
        if profile["description"]:
            bullets.append(f"**Description**: {profile['description']}")
        # Extract h2/h3 headings as feature categories
        feature_headings = [h["text"] for h in profile["headings"] if h.get("level") in (2, 3)][:8]
        if feature_headings:
            bullets.append(f"**Key Sections**: {', '.join(feature_headings)}")
        if profile["ctas"]:
            unique_ctas = list(dict.fromkeys(profile["ctas"]))[:5]
            bullets.append(f"**CTA Signals**: {', '.join(unique_ctas)}")
        if profile["social"]:
            social_items = [f"{k.title()}" for k in profile["social"].keys() if k not in ("email", "phone")]
            if social_items:
                bullets.append(f"**Social Presence**: {', '.join(social_items)}")
            if profile["social"].get("email"):
                bullets.append(f"**Contact Email**: {profile['social']['email']}")
        if not bullets:
            bullets.append(f"Web presence analyzed from scraped content.")
        return "\n".join(f"- {b}" for b in bullets)

    user_features = _extract_feature_bullets(user_profile, user_company_name)
    comp_features = _extract_feature_bullets(competitor_profile, competitor_name)

    # ── Pricing section ──────────────────────────────────────────────────
    pricing_section = ""
    if diffs:
        for d in diffs:
            tier = d.get('tier_name', 'General')
            old_p = d.get('old_price')
            new_p = d.get('new_price')
            details = d.get('details', '')
            if old_p is not None:
                pricing_section += f"- **{tier}**: `${old_p}` → `${new_p}` ({details})\n"
            else:
                pricing_section += f"- **{tier}**: `${new_p}` — {details}\n"
    else:
        pricing_section = f"- No pricing tier changes detected in this scan cycle.\n"

    # ── Sentiment section ────────────────────────────────────────────────
    sentiment_section = ""
    if sentiment_results:
        for s in sentiment_results:
            topics = ', '.join(s.get('topics', [])) if s.get('topics') else 'general'
            sentiment_section += f"- **Source ({s.get('source_type', 'web')})**: Score `{s.get('score')}` ({s.get('sentiment_category', 'neutral')}) | Topics: {topics}\n"
    else:
        sentiment_section = "- No sentiment data available for this analysis cycle.\n"

    # ── Pages analyzed ───────────────────────────────────────────────────
    pages_section = ""
    for p in pages_summary:
        status = "Stale" if p.get("is_stale") else "Valid"
        pages_section += f"- **{p.get('url')}**: `{status}` | {p.get('content_length', 0)} chars\n"

    # ── Executive brief from metadata ────────────────────────────────────
    user_desc_brief = user_profile["description"][:200] if user_profile["description"] else f"{user_company_name}'s web presence"
    comp_desc_brief = competitor_profile["description"][:200] if competitor_profile["description"] else f"{competitor_name}'s web presence"

    structured_report = f"""# Competitive Intelligence Executive Summary: {user_company_name} vs {competitor_name}

{stale_notice}
## Executive Brief
Automated multi-agent intelligence analysis completed between **{user_company_name}** ({user_company_url or 'Primary Site'}) and **{competitor_name}**.

- **{user_company_name}**: {user_desc_brief}
- **{competitor_name}**: {comp_desc_brief}

## 1. Feature & Capability Comparison

### {user_company_name}
{user_features}

### {competitor_name}
{comp_features}

## 2. Pricing & Tier Structure Comparison
{pricing_section}

## 3. Key Advantages of {user_company_name} over {competitor_name}
- Analysis based on {len([p for p in pages_summary if not p.get('is_stale')])} successfully scraped pages.
- Refer to the feature comparison above for detailed capability differences.
- CTA signals suggest go-to-market positioning: {', '.join(list(dict.fromkeys(user_profile['ctas']))[:3]) if user_profile['ctas'] else 'N/A'}

## 4. Key Disadvantages & Gaps of {user_company_name} vs {competitor_name}
- Competitor CTA signals indicate: {', '.join(list(dict.fromkeys(competitor_profile['ctas']))[:3]) if competitor_profile['ctas'] else 'N/A'}
- Competitor social presence: {', '.join(k.title() for k in competitor_profile['social'].keys() if k not in ('email', 'phone')) if competitor_profile['social'] else 'Not detected'}

## 5. Sentiment & Market Perception Analysis
{sentiment_section}

## 6. Strategic Recommendations & Action Plan
1. **Monitor Competitor Changes**: Set weekly monitoring cadences to capture price adjustments or feature rollouts by {competitor_name}.
2. **Leverage Intelligence Data**: Use the scraped content and extracted metadata to inform marketing positioning and sales battle cards.
3. **Run LLM-Powered Analysis**: Configure an OpenRouter API key (LLM_PROVIDER=openrouter) to enable AI-generated deep analysis with specific competitive insights.

### Data Sources Analyzed
{pages_section}
"""
    return structured_report, "instant/structured_comparative_generator"


def generate_rag_answer(
    question: str,
    retrieved_chunks: List[Dict[str, Any]],
    chat_history: Optional[List[Dict[str, str]]] = None,
    image_url: Optional[str] = None,
    media_filename: Optional[str] = None,
    media_type: Optional[str] = None,
    media_content: Optional[str] = None,
    target_competitor_name: Optional[str] = None,
) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Generates grounded RAG answer from retrieved FAISS vector chunks.
    Supports chat memory (conversation history context), image attachments, and document text attachments.
    Returns (answer_markdown, cited_snapshots_list).
    """
    if not retrieved_chunks:
        return "I cannot answer this question based on the available competitive snapshots.", []

    formatted_context = ""
    cited_snapshots = []

    for idx, chunk in enumerate(retrieved_chunks, 1):
        snapshot_id = chunk.get("snapshot_id", "Unknown")
        fetched_at = chunk.get("fetched_at", "Unknown Date")
        source_type = chunk.get("source_type", "web")
        chunk_text = chunk.get("chunk_text", "")

        formatted_context += f"--- Snapshot [{idx}] (ID: {snapshot_id} | Fetched: {fetched_at} | Source: {source_type}) ---\n{chunk_text}\n\n"
        
        cited_snapshots.append({
            "snapshot_id": snapshot_id,
            "fetched_at": fetched_at,
            "source_type": source_type,
            "snippet": chunk_text[:150] + "...",
        })

    # Conversation History Memory Context
    history_context = ""
    if chat_history:
        history_lines = []
        for msg in chat_history[-6:]:
            role = "User" if (msg.get("role") == "user" or msg.get("sender") == "user") else "Assistant"
            text = msg.get("content") or msg.get("text") or ""
            if text:
                history_lines.append(f"{role}: {text}")
        if history_lines:
            history_context = "CONVERSATION MEMORY (PRIOR DIALOGUE TURNS):\n" + "\n".join(history_lines) + "\n\n"

    # Media & Document Attachment Context
    media_context = ""
    if image_url or media_filename or media_content:
        m_label = (media_type or "attachment").upper()
        media_context = f"ATTACHED {m_label} / MEDIA CONTEXT:\n- File Name: {media_filename or 'Attached File'}\n"
        if media_content:
            media_context += f"- Extracted Document Text:\n{media_content[:3500]}\n"
        if image_url:
            media_context += f"- Visual Media: Attached image file ({media_filename or 'Screenshot'})\n"
        media_context += "- Instruction: Analyze and incorporate specific details from this attached document/media into your response.\n\n"

    target_focus = ""
    if target_competitor_name:
        target_focus = (
            f"5. TARGET COMPETITOR FOCUS: The user is currently chatting about target competitor '{target_competitor_name}'.\n"
            f"   Answer directly and specifically about {target_competitor_name}. Do NOT include unrequested sections for other companies unless the user explicitly asks for a comparison.\n"
        )

    prompt = f"""You are an Executive Competitive Intelligence RAG Assistant.

CRITICAL INSTRUCTIONS:
1. Answer the user's question STRICTLY using the provided retrieved snapshot context and conversation memory for the current user's tracked competitors ONLY.
2. Under no circumstances must you disclose or reference information about competitors not belonging to the current user or outside the provided context.
3. DO NOT make assumptions beyond what is explicitly stated in the context or attached media.
4. If the retrieved context does NOT contain sufficient information about the user's tracked competitors, respond EXACTLY: "I cannot answer this question based on your tracked competitor data."
{target_focus}6. FORMAT YOUR ANSWER BEAUTIFULLY:
   - Use bold section headings (e.g. ### Executive Summary, ### Key Analysis, ### Pricing & Features).
   - Use bullet points with bold lead labels (e.g. - **Feature**: details).
   - Keep answers crisp, scannable, and directly focused on the user's query.

{history_context}{media_context}RETRIEVED COMPETITOR SNAPSHOT CONTEXT:
{formatted_context}

USER QUESTION:
{question}

STRUCTURED ANSWER:"""

    provider = (settings.LLM_PROVIDER or "").lower().strip()
    api_key = settings.LLM_API_KEY or ""

    if provider == "openrouter" and api_key:
        try:
            answer_text, _ = call_openrouter(prompt, api_key)
            return answer_text, cited_snapshots
        except Exception as exc:
            print(f"[RAG LLM Error] {exc}. Falling back to deterministic RAG synthesis.")

    # Keyless / Fallback RAG synthesis: extract targeted section if user asked a specific question
    first_chunk = retrieved_chunks[0]['chunk_text'] if retrieved_chunks else "No snapshot context available."
    first_meta = cited_snapshots[0] if cited_snapshots else {"fetched_at": "N/A", "source_type": "database"}
    q_lower = question.lower().strip()

    extracted_content = ""

    # Smart section extraction if context is an executive report document
    if "# Competitive Intelligence Executive Summary" in first_chunk or "## " in first_chunk:
        sections = first_chunk.split("## ")
        for sec in sections:
            if not sec.strip():
                continue
            sec_heading = sec.split("\n")[0].lower()
            if any(k in q_lower for k in ["strength", "advantage", "benefit", "better", "pro", "over"]):
                if any(x in sec_heading for x in ["advantage", "3.", "feature", "1."]):
                    extracted_content += f"### {sec.strip()}\n\n"
            elif any(k in q_lower for k in ["weakness", "gap", "disadvantage", "con", "lacking", "flaw"]):
                if any(x in sec_heading for x in ["disadvantage", "gap", "4."]):
                    extracted_content += f"### {sec.strip()}\n\n"
            elif any(k in q_lower for k in ["price", "cost", "tier", "plan", "fee", "rate"]):
                if any(x in sec_heading for x in ["pricing", "2."]):
                    extracted_content += f"### {sec.strip()}\n\n"
            elif any(k in q_lower for k in ["sentiment", "perception", "rating", "review", "score"]):
                if any(x in sec_heading for x in ["sentiment", "5."]):
                    extracted_content += f"### {sec.strip()}\n\n"
            elif any(k in q_lower for k in ["recommend", "action", "strategy", "plan"]):
                if any(x in sec_heading for x in ["recommendation", "6."]):
                    extracted_content += f"### {sec.strip()}\n\n"

    if not extracted_content.strip():
        extracted_content = first_chunk

    fallback_answer = (
        f"### Executive Intelligence Summary\n"
        f"Grounded in snapshot context fetched on **{first_meta['fetched_at']}** ({first_meta['source_type']}):\n\n"
        f"{extracted_content.strip()}"
    )
    return fallback_answer, cited_snapshots
