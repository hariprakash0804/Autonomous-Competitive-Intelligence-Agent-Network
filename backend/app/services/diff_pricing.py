import re
import json
from typing import List, Dict, Any, Optional

from app.config import settings

# Core plan tier names commonly used in software/SaaS pricing pages
TARGET_TIERS = [
    "Free",
    "Starter",
    "Basic",
    "Standard",
    "Plus",
    "Pro",
    "Team",
    "Business",
    "Enterprise",
    "Developer",
    "Growth",
    "Premium",
    "Ultra",
    "Lite",
    "Flex",
    "Pay-As-You-Go",
    "API",
]

# Regex patterns to detect price values following a tier header
PRICE_PATTERNS = [
    # Monthly/annual user subscriptions e.g. $20/mo, $25/user/month, $200/month
    r"(?:starting\s+at\s+|from\s+)?[\$\€\£]\s*(\d+(?:\.\d{2})?)\s*(?:USD|EUR|GBP)?(?:\s*(?:per|/)\s*(?:user/month|user/mo|month|mo|year|yr))?",
    # Per-token / usage rates e.g. $0.05 / 1M tokens, $0.59/M tokens
    r"[\$\€\£]\s*(\d+(?:\.\d+)?)\s*(?:/|per|\s+per\s+)\s*(?:1m|m|million|100k|k|token|tokens)",
    # Fallback dollar price e.g. $20, $200, $0
    r"[\$\€\£]\s*(\d+(?:\.\d{2})?)",
]


def extract_plan_prices(text: str) -> List[Dict[str, Any]]:
    """
    Extracts distinct plan tiers (Free, Team, Pro, Enterprise, etc.) and binds them
    to their actual price values extracted from surrounding text. Evaluates all occurrences
    of a tier name to select the true pricing card header.
    Filters out false positives from navigation text (e.g. 'Free API key', 'Free trial').
    """
    if not text:
        return []

    # Context phrases that indicate a tier name is used as a nav/CTA element, not a pricing card
    _NAV_CONTEXT_PHRASES = [
        "free api key", "free trial", "free sign up", "free signup", "free account",
        "start free", "try free", "get started free", "sign up free", "free download",
        "free demo", "start building", "get free", "free access",
    ]

    results = []

    for tier in TARGET_TIERS:
        tier_pattern = re.compile(r"\b" + tier + r"\b", re.IGNORECASE)
        matches = list(tier_pattern.finditer(text))
        if not matches:
            continue

        best_candidate: Optional[Dict[str, Any]] = None

        for match in matches:
            start_pos = match.start()
            # Inspect 150 characters right after the tier name
            forward_window = text[start_pos : min(len(text), start_pos + 180)]

            # Skip if this is a navigation/CTA context (e.g. "Free API key", "Free trial")
            forward_lower = forward_window[:60].lower()
            if any(phrase in forward_lower for phrase in _NAV_CONTEXT_PHRASES):
                continue

            for pattern in PRICE_PATTERNS:
                price_match = re.search(pattern, forward_window, re.IGNORECASE)
                if price_match:
                    try:
                        val_float = float(price_match.group(1))
                        matched_str = price_match.group(0).strip()
                        distance = price_match.start()

                        # Prefer non-zero prices for non-Free tiers (prevents intro text like 'team... $0' from matching Free card)
                        is_better = False
                        if best_candidate is None or best_candidate.get("price") is None:
                            is_better = True
                        else:
                            best_val = best_candidate["price"]
                            if tier.lower() != "free":
                                if best_val == 0.0 and val_float > 0.0:
                                    is_better = True
                                elif (best_val == 0.0 or val_float > 0.0) and distance < best_candidate.get("distance", 999):
                                    is_better = True
                            else:
                                if distance < best_candidate.get("distance", 999):
                                    is_better = True

                        if is_better:
                            best_candidate = {
                                "tier_name": tier.capitalize(),
                                "price": val_float,
                                "price_str": matched_str,
                                "distance": distance,
                            }
                        break
                    except ValueError:
                        continue

        # Only set Contact Us / Custom if no numeric price candidate was found across all matches
        if best_candidate is None:
            # Check full text for custom/contact tier mentions
            for match in matches:
                forward_window = text[match.start() : min(len(text), match.start() + 180)]
                if "contact" in forward_window.lower() or "custom" in forward_window.lower() or "enterprise" in tier.lower():
                    best_candidate = {
                        "tier_name": tier.capitalize(),
                        "price": None,
                        "price_str": "Contact Us / Custom",
                    }
                    break

        if best_candidate:
            # Remove helper distance key
            best_candidate.pop("distance", None)
            results.append(best_candidate)

    return results


def _regex_diff_pricing(old_text: str, new_text: str) -> List[Dict[str, Any]]:
    """Original regex-based pricing diff (fast, no API calls)."""
    new_plans = extract_plan_prices(new_text)

    if not old_text:
        changes = []
        for item in new_plans:
            changes.append({
                "tier_name": item["tier_name"],
                "old_price": None,
                "new_price": item["price"],
                "details": f"Initial baseline price detected for {item['tier_name']}: ${item['price']} ({item['price_str']})"
                if item["price"] is not None
                else f"Initial baseline detected for {item['tier_name']}: {item['price_str']}",
            })
        return changes

    old_plans = extract_plan_prices(old_text)
    old_map = {item["tier_name"]: item for item in old_plans}
    new_map = {item["tier_name"]: item for item in new_plans}

    changes = []
    for tier, new_item in new_map.items():
        if tier in old_map:
            old_item = old_map[tier]
            if old_item["price"] != new_item["price"]:
                changes.append({
                    "tier_name": tier,
                    "old_price": old_item["price"],
                    "new_price": new_item["price"],
                    "details": f"Price updated for {tier}: ${old_item['price']} -> ${new_item['price']}",
                })
        else:
            changes.append({
                "tier_name": tier,
                "old_price": None,
                "new_price": new_item["price"],
                "details": f"New plan tier added: {tier} (${new_item['price']})",
            })

    for tier, old_item in old_map.items():
        if tier not in new_map:
            changes.append({
                "tier_name": tier,
                "old_price": old_item["price"],
                "new_price": None,
                "details": f"Plan tier no longer listed: {tier}",
            })

    return changes


_LLM_PRICING_CACHE: Dict[str, List[Dict[str, Any]]] = {}


def _llm_extract_pricing(text: str) -> List[Dict[str, Any]]:
    """
    LLM-powered pricing extraction that can detect ANY pricing structure,
    not just hardcoded tier names. Handles custom tier names, usage-based pricing,
    per-seat pricing, and complex pricing tables.
    """
    from app.services.llm import call_openrouter
    import hashlib

    if not text:
        return []

    cache_key = hashlib.md5(text[:4000].encode("utf-8")).hexdigest()
    if cache_key in _LLM_PRICING_CACHE:
        print(f"[LLM Pricing Cache] Hit for text hash {cache_key[:8]}", flush=True)
        return _LLM_PRICING_CACHE[cache_key]

    api_key = settings.LLM_API_KEY or ""
    if not api_key:
        return extract_plan_prices(text)

    sample_text = text[:4000]

    prompt = f"""Extract ALL real subscription/pricing tiers from this pricing page content.

IMPORTANT RULES:
- Only extract REAL pricing plans/tiers with actual dollar amounts or "Contact Us" pricing.
- Do NOT extract navigation menu items, button labels, page headers, or feature names as tiers.
- Do NOT extract per-token API pricing rows as subscription tiers (those are usage-based rates, not plans).
- A valid tier must have a plan NAME and a monthly/yearly PRICE or "Contact Us".
- If no real subscription tiers are found, return an empty array [].

CONTENT:
{sample_text}

Respond ONLY with valid JSON array (no markdown, no extra text). Each item must have:
[
  {{
    "tier_name": "<plan name>",
    "price": <numeric price or null if contact-us/custom>,
    "price_str": "<price as shown, e.g. '$20/mo per user'>",
    "billing_period": "<monthly|yearly|one-time|usage-based|custom>",
    "key_features": ["<feature1>", "<feature2>"]
  }}
]

If no real pricing tiers are found, return: []"""

    try:
        response_text, model_used = call_openrouter(prompt, api_key)
        print(f"[LLM Pricing] Extraction completed via {model_used}", flush=True)

        json_text = response_text.strip()
        if json_text.startswith("```"):
            json_text = re.sub(r"```(?:json)?\s*", "", json_text)
            json_text = json_text.rstrip("`").strip()

        parsed = json.loads(json_text)
        if not isinstance(parsed, list):
            parsed = [parsed]

        # Normalize to standard format
        results = []
        for item in parsed:
            price_val = item.get("price")
            if isinstance(price_val, str):
                # Try to extract numeric from string
                nums = re.findall(r"[\d.]+", price_val)
                price_val = float(nums[0]) if nums else None
            elif isinstance(price_val, (int, float)):
                price_val = float(price_val)
            else:
                price_val = None

            results.append({
                "tier_name": str(item.get("tier_name", "Unknown")),
                "price": price_val,
                "price_str": str(item.get("price_str", f"${price_val}" if price_val else "Custom")),
                "billing_period": str(item.get("billing_period", "monthly")),
                "key_features": item.get("key_features", []),
            })

        _LLM_PRICING_CACHE[cache_key] = results
        return results

    except json.JSONDecodeError as e:
        print(f"[LLM Pricing] JSON parse failed: {e}. Falling back to regex.", flush=True)
        return extract_plan_prices(text)
    except Exception as e:
        print(f"[LLM Pricing] LLM call failed: {e}. Falling back to regex.", flush=True)
        return extract_plan_prices(text)


def smart_extract_plan_prices(text: str) -> List[Dict[str, Any]]:
    """
    Unified high-speed pricing plan extractor.
    1. Try fast local regex extraction first (sub-millisecond execution).
    2. Fall back to LLM extraction only if regex finds 0 plans.
    """
    regex_plans = extract_plan_prices(text)
    if regex_plans:
        return regex_plans

    provider = (settings.LLM_PROVIDER or "").lower().strip()
    api_key = settings.LLM_API_KEY or ""

    if provider == "openrouter" and api_key:
        plans = _llm_extract_pricing(text)
        if plans:
            return plans

    return regex_plans


def diff_pricing(old_text: str, new_text: str) -> List[Dict[str, Any]]:
    """
    Smart pricing diff that uses LLM for extraction when available.
    - If LLM_PROVIDER=openrouter and LLM_API_KEY is set → LLM extracts ANY pricing structure
    - Otherwise → regex-based extraction with hardcoded tier patterns
    Both return the same interface: [{tier_name, old_price, new_price, details}]
    """
    provider = (settings.LLM_PROVIDER or "").lower().strip()
    api_key = settings.LLM_API_KEY or ""

    if provider == "openrouter" and api_key:
        return _llm_diff_pricing(old_text, new_text)

    return _regex_diff_pricing(old_text, new_text)


def _llm_diff_pricing(old_text: str, new_text: str) -> List[Dict[str, Any]]:
    """Uses LLM to extract prices from both texts and computes the diff."""
    new_plans = _llm_extract_pricing(new_text)

    if not old_text:
        # First snapshot — register baseline
        changes = []
        for item in new_plans:
            changes.append({
                "tier_name": item["tier_name"],
                "old_price": None,
                "new_price": item["price"],
                "details": f"Initial baseline: {item['tier_name']} at {item['price_str']}"
                + (f" ({item.get('billing_period', '')})" if item.get("billing_period") else ""),
            })
        return changes

    # For the old text, use regex (faster, no extra API call) since we just need tier→price mapping
    old_plans = extract_plan_prices(old_text)
    old_map = {item["tier_name"]: item for item in old_plans}
    new_map = {item["tier_name"]: item for item in new_plans}

    changes = []
    for tier, new_item in new_map.items():
        if tier in old_map:
            old_item = old_map[tier]
            if old_item["price"] != new_item["price"]:
                changes.append({
                    "tier_name": tier,
                    "old_price": old_item["price"],
                    "new_price": new_item["price"],
                    "details": f"Price changed for {tier}: ${old_item['price']} -> ${new_item['price']}",
                })
        else:
            changes.append({
                "tier_name": tier,
                "old_price": None,
                "new_price": new_item["price"],
                "details": f"New plan detected: {tier} ({new_item.get('price_str', '')})",
            })

    for tier, old_item in old_map.items():
        if tier not in new_map:
            changes.append({
                "tier_name": tier,
                "old_price": old_item["price"],
                "new_price": None,
                "details": f"Plan tier no longer listed: {tier}",
            })

    return changes
