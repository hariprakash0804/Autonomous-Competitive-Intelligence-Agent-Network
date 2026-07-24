import sys
import json
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.services.scraper import scrape_url
from app.services.diff_pricing import diff_pricing, extract_plan_prices

def test_extraction():
    for name, url in [("GitHub", "https://github.com/pricing"), ("Supabase", "https://supabase.com/pricing")]:
        res = scrape_url(url)
        text = res["clean_text"]
        plans = extract_plan_prices(text)
        print(f"================ {name} ({url}) ================")
        print("Extracted Plans:")
        for p in plans:
            print(f"  Tier: {p['tier_name']:<12} | Price: {str(p['price']):<8} | Raw String: {p['price_str']}")

        changes = diff_pricing("", text)
        print("\nDiff Pricing (First Run Baseline):")
        for c in changes:
            print(f"  Tier: {c['tier_name']:<12} | Old: {str(c['old_price']):<8} | New: {str(c['new_price']):<8} | Details: {c['details']}")
        print("\n")

if __name__ == "__main__":
    test_extraction()
