import hashlib
import re
from typing import Dict, Any, Tuple
import httpx
from bs4 import BeautifulSoup

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

# Common indicators of a JS-rendered empty shell or bot protection page
JS_SHELL_PATTERNS = [
    r"javascript is required",
    r"enable javascript",
    r"you need to enable javascript to run this app",
    r"please enable javascript",
    r"checking your browser before accessing",
    r"enable cookies and reload",
]

MIN_CONTENT_LENGTH = 100


def clean_html(html_content: str) -> str:
    """Strips script, style tags, and extracts visible text content from HTML."""
    soup = BeautifulSoup(html_content, "lxml")
    for script_or_style in soup(["script", "style", "noscript", "svg", "header", "footer", "nav"]):
        script_or_style.decompose()

    text = soup.get_text(separator=" ", strip=True)
    # Normalize multiple whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text


def compute_content_hash(text: str) -> str:
    """Returns SHA-256 hash of string content."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def check_is_stale(html: str, clean_text: str, status_code: int) -> Tuple[bool, str | None]:
    """
    Evaluates whether the scraped content is empty or a JS-render shell.
    Returns (is_stale, reason).
    """
    if status_code != 200:
        return True, f"HTTP status {status_code}"

    if not clean_text or len(clean_text) < MIN_CONTENT_LENGTH:
        return True, f"Content length too short ({len(clean_text)} chars)"

    lower_text = clean_text.lower()
    lower_html = html.lower()

    for pattern in JS_SHELL_PATTERNS:
        if re.search(pattern, lower_text) or re.search(pattern, lower_html):
            return True, f"Detected JS shell pattern matching '{pattern}'"

    return False, None


async def scrape_url_async(url: str, timeout: float = 15.0) -> Dict[str, Any]:
    """
    Asynchronously fetches a URL using httpx and extracts clean text.
    Flags is_stale=True if HTTP fails or content appears to be a JS shell.
    """
    headers = {"User-Agent": DEFAULT_USER_AGENT}
    try:
        async with httpx.AsyncClient(headers=headers, follow_redirects=True, timeout=timeout) as client:
            response = await client.get(url)
            status_code = response.status_code
            html_content = response.text
    except Exception as exc:
        return {
            "url": url,
            "raw_content": "",
            "clean_text": "",
            "content_hash": "",
            "is_stale": True,
            "stale_reason": f"Network or HTTP error: {str(exc)}",
            "status_code": 0,
        }

    clean_text = clean_html(html_content)
    is_stale, stale_reason = check_is_stale(html_content, clean_text, status_code)
    content_hash = compute_content_hash(clean_text)

    return {
        "url": url,
        "raw_content": html_content,
        "clean_text": clean_text,
        "content_hash": content_hash,
        "is_stale": is_stale,
        "stale_reason": stale_reason,
        "status_code": status_code,
    }


def scrape_url(url: str, timeout: float = 15.0) -> Dict[str, Any]:
    """
    Synchronous wrapper for scrape_url_async.
    """
    headers = {"User-Agent": DEFAULT_USER_AGENT}
    try:
        with httpx.Client(headers=headers, follow_redirects=True, timeout=timeout) as client:
            response = client.get(url)
            status_code = response.status_code
            html_content = response.text
    except Exception as exc:
        return {
            "url": url,
            "raw_content": "",
            "clean_text": "",
            "content_hash": "",
            "is_stale": True,
            "stale_reason": f"Network or HTTP error: {str(exc)}",
            "status_code": 0,
        }

    clean_text = clean_html(html_content)
    is_stale, stale_reason = check_is_stale(html_content, clean_text, status_code)
    content_hash = compute_content_hash(clean_text)

    return {
        "url": url,
        "raw_content": html_content,
        "clean_text": clean_text,
        "content_hash": content_hash,
        "is_stale": is_stale,
        "stale_reason": stale_reason,
        "status_code": status_code,
    }
