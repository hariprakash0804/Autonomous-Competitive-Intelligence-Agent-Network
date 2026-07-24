import re
from typing import List, Dict, Any, Optional

# Core plan tier names commonly used in software/SaaS pricing pages
TARGET_TIERS = [
    "Free",
    "Team",
    "Pro",
    "Enterprise",
    "Basic",
    "Starter",
    "Business",
    "Developer",
    "Growth",
    "Premium",
]

# Regex patterns to detect price values following a tier header
PRICE_PATTERNS = [
    r"(?:starting\s+at\s+|from\s+)?[\$\€\£]\s*(\d+(?:\.\d{2})?)\s*(?:USD|EUR|GBP)?(?:\s*(?:per|/)\s*(?:user/month|user/mo|month|mo|year|yr))?",
    r"(\d+(?:\.\d{2})?)\s*(?:USD|EUR|GBP)\s*(?:per|/)\s*(?:user/month|user/mo|month|mo|year|yr)",
    r"[\$\€\£]\s*(\d+(?:\.\d{2})?)",
]


def extract_plan_prices(text: str) -> List[Dict[str, Any]]:
    """
    Extracts distinct plan tiers (Free, Team, Pro, Enterprise, etc.) and binds them
    to their actual price values extracted from surrounding text. Evaluates all occurrences
    of a tier name to select the true pricing card header.
    """
    if not text:
        return []

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

            for pattern in PRICE_PATTERNS:
                price_match = re.search(pattern, forward_window, re.IGNORECASE)
                if price_match:
                    try:
                        val_float = float(price_match.group(1))
                        matched_str = price_match.group(0).strip()
                        distance = price_match.start()

                        # Prefer non-zero prices for non-Free tiers (prevents intro text like 'team... $0' from matching Free card)
                        is_better = False
                        if best_candidate is None:
                            is_better = True
                        else:
                            best_val = best_candidate["price"]
                            if tier.lower() != "free":
                                if best_val == 0.0 and val_float > 0.0:
                                    is_better = True
                                elif (best_val == 0.0 or val_float > 0.0) and distance < best_candidate["distance"]:
                                    is_better = True
                            else:
                                if distance < best_candidate["distance"]:
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

            if best_candidate is None and ("contact" in forward_window.lower() or "custom" in forward_window.lower()):
                best_candidate = {
                    "tier_name": tier.capitalize(),
                    "price": None,
                    "price_str": "Contact Us / Custom",
                    "distance": 999,
                }

        if best_candidate:
            # Remove helper distance key
            best_candidate.pop("distance", None)
            results.append(best_candidate)

    return results


def diff_pricing(old_text: str, new_text: str) -> List[Dict[str, Any]]:
    """
    Compares old vs new pricing page text and returns a list of detected price changes.
    Each item: { tier_name, old_price, new_price, details }
    """
    new_plans = extract_plan_prices(new_text)

    if not old_text:
        # First snapshot: register baseline prices for all extracted distinct plan tiers
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
