import os
import time
from typing import Dict, Any, Tuple, List, Optional
from openai import OpenAI, RateLimitError, APIError

from app.config import settings

# Primary and Fallback active OpenRouter free models
PRIMARY_FREE_MODEL = "google/gemma-4-31b-it:free"
FALLBACK_FREE_MODEL = "nvidia/nemotron-3-nano-30b-a3b:free"
ALTERNATIVE_FREE_MODEL = "meta-llama/llama-3.3-70b-instruct:free"

# Proactive rate-limiting: minimum delay between LLM requests (3 seconds = max 20 requests/minute)
MIN_REQUEST_INTERVAL_SECONDS = 3.0
_last_request_timestamp = 0.0


def _enforce_proactive_rate_limit():
    """Proactively ensures at least 3 seconds between LLM calls to respect 20 req/min limit."""
    global _last_request_timestamp
    elapsed = time.time() - _last_request_timestamp
    if elapsed < MIN_REQUEST_INTERVAL_SECONDS:
        wait_time = MIN_REQUEST_INTERVAL_SECONDS - elapsed
        print(f"[OpenRouter Rate Limit Guard] Waiting {wait_time:.2f}s to respect 20 req/min limit...")
        time.sleep(wait_time)
    _last_request_timestamp = time.time()


def call_openrouter(prompt: str, api_key: str) -> Tuple[str, str]:
    """
    Invokes OpenRouter API using OpenAI SDK with active free model.
    Proactively enforces a 3s delay (20 req/min limit) and reactively catches 429 rate limits
    or API errors to automatically try fallbacks.
    Returns (response_text, actual_model_served).
    """
    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
        default_headers={
            "HTTP-Referer": "https://github.com/Autonomous-Competitive-Intelligence-Agent-Network",
            "X-Title": "Autonomous Competitive Intelligence Agent Network",
        },
    )

    models_to_try = [
        PRIMARY_FREE_MODEL,
        FALLBACK_FREE_MODEL,
        ALTERNATIVE_FREE_MODEL,
    ]
    
    last_exception = None

    for idx, model in enumerate(models_to_try):
        # 1. Proactive Rate Limit Delay
        _enforce_proactive_rate_limit()

        try:
            print(f"[OpenRouter Request] Attempting model '{model}' with 12s HTTP timeout guard...")
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=600,
                timeout=12.0,
            )
            model_served = getattr(response, "model", model)
            content = response.choices[0].message.content or ""
            return content, str(model_served)

        except Exception as exc:
            last_exception = exc
            err_msg = str(exc)
            is_429 = isinstance(exc, RateLimitError) or "429" in err_msg or "rate limit" in err_msg.lower()
            is_404 = getattr(exc, "status_code", None) == 404 or "404" in err_msg or "unavailable for free" in err_msg.lower()

            if is_429:
                print(f"[OpenRouter 429 Rate Limit] Model '{model}' rate-limited. Retrying next candidate in 2s...")
                time.sleep(2.0)
            elif is_404:
                print(f"[OpenRouter 404 Deprecated/Paid] Model '{model}' unavailable for free. Trying fallback candidate...")
            else:
                print(f"[OpenRouter Error/Timeout] Model '{model}' failed: {exc}. Retrying next candidate...")

    raise last_exception if last_exception else RuntimeError("All OpenRouter candidate models failed.")


def generate_executive_report(
    competitor_name: str,
    diffs: list[dict],
    sentiment_results: list[dict],
    pages_summary: list[dict],
    is_incomplete: bool = False,
) -> Tuple[str, str]:
    """
    Generates a structured competitive intelligence report.
    Returns (report_markdown, model_info_string).
    """
    provider = (settings.LLM_PROVIDER or "").lower().strip()
    api_key = settings.LLM_API_KEY or ""

    prompt = f"""
You are an expert Competitive Intelligence Analyst. Generate a concise executive report for '{competitor_name}'.

Data Context:
- Price Changes & Tiers Detected: {diffs}
- Sentiment & Topic Analysis: {sentiment_results}
- Scraped Page Summaries: {pages_summary}
- Incompleteness Flag (Stale Retries Exceeded): {is_incomplete}

Report Structure:
# Competitive Intelligence Executive Summary: {competitor_name}

## Executive Brief
## 1. Key Pricing & Packaging Movements
## 2. Sentiment & Market Perception Analysis
## 3. Web & Content Snapshot Summary
## 4. Strategic Risks & Recommended Counter-Actions
"""

    if is_incomplete:
        prompt += "\nNOTE: Highlight that some page scrapes were flagged stale after maximum retries."

    # 1. OpenRouter Provider Execution
    if provider == "openrouter" and api_key:
        try:
            report_text, model_used = call_openrouter(prompt, api_key)
            return report_text, f"openrouter/{model_used}"
        except Exception as exc:
            print(f"[OpenRouter API Failure] {exc}. Falling back to instant structured mock generator.")

    # 2. Keyless Fallback Instant Report Generator
    stale_notice = (
        "> [!WARNING]\n> **Data Collection Incomplete**: One or more source pages were flagged stale after 2 retries.\n\n"
        if is_incomplete
        else ""
    )

    pricing_section = ""
    if diffs:
        for d in diffs:
            pricing_section += f"- **{d.get('tier_name', 'General')}**: Old Price: `${d.get('old_price', 'None')}` -> New Price: `${d.get('new_price', 'None')}` ({d.get('details', '')})\n"
    else:
        pricing_section = "- No new price changes detected compared to baseline snapshots.\n"

    sentiment_section = ""
    if sentiment_results:
        for s in sentiment_results:
            sentiment_section += f"- **Source ({s.get('source_type')})**: Score `{s.get('score')}` ({s.get('sentiment_category')}) | Key Topics: {', '.join(s.get('topics', []))}\n"
    else:
        sentiment_section = "- Sentiment metrics are within baseline thresholds.\n"

    pages_section = ""
    for p in pages_summary:
        pages_section += f"- **URL**: {p.get('url')} | Status: `{'Stale' if p.get('is_stale') else 'Valid'}` | Length: {p.get('content_length')} chars\n"

    mock_report = f"""# Competitive Intelligence Executive Summary: {competitor_name}

{stale_notice}
## Executive Brief
Automated agent pipeline completed multi-source intelligence gathering for **{competitor_name}**.

## 1. Key Pricing & Packaging Movements
{pricing_section}

## 2. Sentiment & Market Perception Analysis
{sentiment_section}

## 3. Web & Content Snapshot Summary
{pages_section}

## 4. Strategic Risks & Recommended Counter-Actions
- Monitor competitor pricing adjustments for tier positioning response.
- Leverage positive sentiment topics to refine product marketing.
"""
    return mock_report, "instant/structured_generator"


def generate_rag_answer(question: str, retrieved_chunks: List[Dict[str, Any]]) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Grounded RAG Answer Generator using strict context boundaries.
    Answers strictly from retrieved snapshot chunks or explicitly states if context is insufficient.
    Returns (answer_string, list_of_cited_snapshots).
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

    prompt = f"""You are a strict Competitive Intelligence RAG Assistant.

CRITICAL INSTRUCTIONS:
1. Answer the user's question STRICTLY and ONLY using the provided retrieved snapshot context below.
2. DO NOT use your internal general knowledge or make assumptions beyond what is explicitly stated in the context.
3. If the retrieved context does NOT contain sufficient information to answer the question, you MUST respond exactly: "I cannot answer this question based on the available competitive snapshots."
4. Include cited snapshot dates in your explanation when stating facts.

RETRIEVED COMPETITOR SNAPSHOT CONTEXT:
{formatted_context}

USER QUESTION:
{question}

ANSWER:"""

    provider = (settings.LLM_PROVIDER or "").lower().strip()
    api_key = settings.LLM_API_KEY or ""

    if provider == "openrouter" and api_key:
        try:
            answer_text, _ = call_openrouter(prompt, api_key)
            return answer_text, cited_snapshots
        except Exception as exc:
            print(f"[RAG LLM Error] {exc}. Falling back to deterministic RAG synthesis.")

    # Keyless / Fallback RAG synthesis
    fallback_answer = (
        f"Based on the snapshot content fetched on {cited_snapshots[0]['fetched_at']} ({cited_snapshots[0]['source_type']}), "
        f"here is the information found: {retrieved_chunks[0]['chunk_text'][:300]}..."
    )
    return fallback_answer, cited_snapshots
