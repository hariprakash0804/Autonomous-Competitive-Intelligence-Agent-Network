import pytest
from app.services.diff_pricing import extract_plan_prices, _regex_diff_pricing


def test_extract_plan_prices():
    sample_pricing_text = """
    Our Pricing Plans:
    Free Plan
    $0.00 / Free
    Access basic features for 1 user.

    Pro Plan
    $29/mo per user
    Advanced workflows, unlimited storage, priority support.

    Enterprise Plan
    Contact Us / Custom
    Dedicated account manager and custom SLA.
    """
    plans = extract_plan_prices(sample_pricing_text)
    assert len(plans) >= 2
    tier_names = [p["tier_name"] for p in plans]
    assert "Free" in tier_names
    assert "Pro" in tier_names

    free_tier = next(p for p in plans if p["tier_name"] == "Free")
    assert free_tier["price"] == 0.0

    pro_tier = next(p for p in plans if p["tier_name"] == "Pro")
    assert pro_tier["price"] == 29.0


def test_diff_pricing_baseline():
    text = "Starter Plan $10/mo\nPro Plan $30/mo"
    changes = _regex_diff_pricing(old_text="", new_text=text)
    assert len(changes) >= 2
    assert all(c["old_price"] is None for c in changes)


def test_diff_pricing_price_update():
    old_text = "Pro Plan $25/mo\nStarter Plan $10/mo"
    new_text = "Pro Plan $35/mo\nStarter Plan $10/mo"
    changes = _regex_diff_pricing(old_text=old_text, new_text=new_text)
    assert len(changes) >= 1
    pro_change = next((c for c in changes if c["tier_name"] == "Pro"), None)
    assert pro_change is not None
    assert pro_change["old_price"] == 25.0
    assert pro_change["new_price"] == 35.0
