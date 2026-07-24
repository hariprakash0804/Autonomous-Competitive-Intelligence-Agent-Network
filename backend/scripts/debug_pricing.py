import sys
import re
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.services.scraper import scrape_url

def inspect_pricing():
    for name, url in [("GitHub", "https://github.com/pricing"), ("Supabase", "https://supabase.com/pricing")]:
        res = scrape_url(url)
        text = res["clean_text"]
        print(f"================ {name} ({url}) ================")
        print(f"Total Text Length: {len(text)}")
        # Search for occurrences of plan keywords in text
        for tier in ["Free", "Team", "Enterprise", "Pro", "Pay as you go"]:
            matches = [m.start() for m in re.finditer(r"\b" + tier + r"\b", text, re.IGNORECASE)]
            print(f"\nKeyword '{tier}' found {len(matches)} times.")
            for idx in matches[:3]:
                snippet = text[max(0, idx-50): min(len(text), idx+150)]
                print(f"  Snippet around pos {idx}: {snippet!r}")

if __name__ == "__main__":
    inspect_pricing()
