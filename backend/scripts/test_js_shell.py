import sys
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.services.scraper import scrape_url

SPA_TEST_URLS = [
    "https://trello.com/login",
    "https://app.asana.com/",
    "https://client.schwab.com/",
    "https://chatgpt.com",
]

def test_spa_urls():
    print("=========================================================================")
    print("TESTING REAL JS-SHELL / SPA URLS FOR JS MARKER DETECTION")
    print("=========================================================================\n")
    for url in SPA_TEST_URLS:
        res = scrape_url(url)
        print(f"URL: {url}")
        print(f"  HTTP Status   : {res['status_code']}")
        print(f"  is_stale      : {res['is_stale']}")
        print(f"  stale_reason  : {res['stale_reason']}")
        print(f"  clean_text snippet: {res['clean_text'][:150]!r}\n")

if __name__ == "__main__":
    test_spa_urls()
