import hashlib
import json
import re
import time
import random
from typing import Dict, Any, List, Tuple, Optional
from urllib.parse import urlparse, urljoin
import httpx
from bs4 import BeautifulSoup

# ── Rotating User-Agents to avoid bot detection ──────────────────────────────
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.5; rv:128.0) Gecko/20100101 Firefox/128.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36 Edg/126.0.0.0",
]

# ── JS-shell / bot-block detection patterns ───────────────────────────────────
JS_SHELL_PATTERNS = [
    r"javascript is required",
    r"enable javascript",
    r"you need to enable javascript to run this app",
    r"please enable javascript",
    r"checking your browser before accessing",
    r"enable cookies and reload",
    r"just a moment\.\.\.",
    r"attention required.*cloudflare",
    r"ray id:",
    r"cf-browser-verification",
    r"_cf_chl_opt",
    r"captcha-delivery",
    r"access denied.*security",
    r"bot detection",
    r"are you a robot",
    r"verify you are human",
]

MIN_CONTENT_LENGTH = 100
MAX_RESPONSE_BYTES = 10 * 1024 * 1024  # 10MB safety cap


def _get_random_ua() -> str:
    """Returns a random realistic browser User-Agent."""
    return random.choice(USER_AGENTS)


def _build_browser_headers(url: str) -> Dict[str, str]:
    """
    Builds a full set of browser-like headers tailored to the target domain.
    This dramatically reduces bot detection compared to a bare User-Agent.
    """
    parsed = urlparse(url)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    ua = _get_random_ua()

    headers = {
        "User-Agent": ua,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/json,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Referer": origin + "/",
        "Cache-Control": "max-age=0",
    }

    # Add Chromium sec-ch-ua headers if UA is Chrome-based
    if "Chrome" in ua:
        headers["sec-ch-ua"] = '"Chromium";v="126", "Google Chrome";v="126", "Not-A.Brand";v="8"'
        headers["sec-ch-ua-mobile"] = "?0"
        headers["sec-ch-ua-platform"] = '"Windows"'

    return headers


def _validate_url(url: str) -> Tuple[bool, str]:
    """Validates and normalizes a URL. Returns (is_valid, normalized_url_or_error)."""
    if not url or not url.strip():
        return False, "Empty URL"

    url = url.strip()

    # Add scheme if missing
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    try:
        parsed = urlparse(url)
        if not parsed.netloc:
            return False, f"No valid domain in URL: {url}"
        if parsed.scheme not in ("http", "https"):
            return False, f"Unsupported scheme: {parsed.scheme}"
        return True, url
    except Exception as e:
        return False, f"URL parse error: {e}"


def _detect_content_type(response: httpx.Response) -> str:
    """Detects the content type from response headers. Returns: 'html', 'json', 'xml', 'text', or 'binary'."""
    ct = (response.headers.get("content-type") or "").lower()

    if "html" in ct:
        return "html"
    elif "json" in ct:
        return "json"
    elif "xml" in ct or "rss" in ct or "atom" in ct:
        return "xml"
    elif "text/" in ct:
        return "text"
    else:
        # Fallback: try to detect from content
        try:
            text_start = response.text[:500].strip().lower()
            if text_start.startswith(("<!doctype", "<html", "<head", "<body", "<!--")):
                return "html"
            elif text_start.startswith(("{", "[")):
                return "json"
            elif text_start.startswith(("<?xml", "<rss", "<feed")):
                return "xml"
        except Exception:
            pass
        return "text"


def clean_html(html_content: str) -> str:
    """Strips script, style tags, and extracts visible text content from HTML."""
    if not html_content:
        return ""
    try:
        soup = BeautifulSoup(html_content, "lxml")
    except Exception:
        # Fallback to html.parser if lxml is not available or fails
        try:
            soup = BeautifulSoup(html_content, "html.parser")
        except Exception:
            return ""

    for tag in soup(["script", "style", "noscript", "svg", "header", "footer", "nav", "iframe"]):
        tag.decompose()

    text = soup.get_text(separator=" ", strip=True)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def clean_json_content(json_text: str) -> str:
    """Extracts readable text from JSON responses (API endpoints, structured data)."""
    try:
        data = json.loads(json_text)
        return _flatten_json(data)
    except (json.JSONDecodeError, ValueError):
        return json_text[:5000]


def _flatten_json(obj: Any, max_depth: int = 5, _depth: int = 0) -> str:
    """Recursively flattens a JSON object into readable text."""
    if _depth > max_depth:
        return ""

    if isinstance(obj, str):
        return obj
    elif isinstance(obj, (int, float, bool)):
        return str(obj)
    elif isinstance(obj, list):
        parts = []
        for item in obj[:50]:  # Cap list items to avoid explosion
            part = _flatten_json(item, max_depth, _depth + 1)
            if part:
                parts.append(part)
        return " ".join(parts)
    elif isinstance(obj, dict):
        parts = []
        for key, value in list(obj.items())[:50]:  # Cap dict keys
            val_str = _flatten_json(value, max_depth, _depth + 1)
            if val_str:
                parts.append(f"{key}: {val_str}")
        return " | ".join(parts)
    return ""


def clean_xml_content(xml_text: str) -> str:
    """Extracts readable text from XML/RSS/Atom feeds."""
    try:
        soup = BeautifulSoup(xml_text, "lxml-xml")
    except Exception:
        try:
            soup = BeautifulSoup(xml_text, "html.parser")
        except Exception:
            return xml_text[:5000]

    for tag in soup(["script", "style"]):
        tag.decompose()

    text = soup.get_text(separator=" ", strip=True)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def compute_content_hash(text: str) -> str:
    """Returns SHA-256 hash of string content."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def check_is_stale(html: str, clean_text: str, status_code: int) -> Tuple[bool, Optional[str]]:
    """
    Evaluates whether the scraped content is empty, a JS-render shell,
    or blocked by bot detection.
    """
    # Accept any 2xx status code, not just exactly 200
    if status_code < 200 or status_code >= 400:
        return True, f"HTTP status {status_code}"

    if not clean_text or len(clean_text) < MIN_CONTENT_LENGTH:
        return True, f"Content length too short ({len(clean_text) if clean_text else 0} chars)"

    lower_text = clean_text.lower()
    lower_html = html.lower() if html else ""

    for pattern in JS_SHELL_PATTERNS:
        if re.search(pattern, lower_text) or re.search(pattern, lower_html):
            # Only flag as stale if the total content is very short (actual pages may contain these phrases incidentally)
            if len(clean_text) < 500:
                return True, f"Detected JS shell / bot-block pattern: '{pattern}'"

    return False, None


def _extract_text_by_content_type(response: httpx.Response, content_type: str) -> str:
    """Extracts clean text from a response based on its detected content type."""
    raw_text = response.text

    if content_type == "html":
        return clean_html(raw_text)
    elif content_type == "json":
        return clean_json_content(raw_text)
    elif content_type == "xml":
        return clean_xml_content(raw_text)
    else:
        # Plain text — just clean up whitespace
        return re.sub(r"\s+", " ", raw_text).strip()[:10000]


def scrape_url(url: str, timeout_sec: float = 10.0, max_retries: int = 2) -> Dict[str, Any]:
    """
    Robust synchronous HTTP scraper that handles any URL type:
    - Static HTML pages, SPAs, API endpoints (JSON), RSS/XML feeds, plain text
    - Rotating User-Agents + full browser-like headers to avoid bot detection
    - Automatic retry with backoff on transient failures (429, 500, 502, 503, 504, timeouts)
    - SSL error fallback (retries without strict verification)
    - Content-type auto-detection for HTML/JSON/XML/text
    - URL validation and normalization (adds https:// if missing)
    - Response size cap (10MB) to avoid memory issues
    """
    # 1. Validate and normalize URL
    is_valid, url_or_error = _validate_url(url)
    if not is_valid:
        return {
            "url": url,
            "raw_content": "",
            "clean_text": "",
            "content_hash": "",
            "is_stale": True,
            "stale_reason": f"Invalid URL: {url_or_error}",
            "status_code": 0,
        }
    url = url_or_error

    # 2. Retry loop with exponential backoff
    last_error = None
    verify_ssl = True

    for attempt in range(max_retries + 1):
        headers = _build_browser_headers(url)
        timeout_config = httpx.Timeout(timeout_sec, connect=5.0)

        try:
            with httpx.Client(
                headers=headers,
                follow_redirects=True,
                timeout=timeout_config,
                verify=verify_ssl,
                max_redirects=10,
            ) as client:
                response = client.get(url)
                status_code = response.status_code

                # Check response size before reading full body
                content_length = int(response.headers.get("content-length", 0))
                if content_length > MAX_RESPONSE_BYTES:
                    return {
                        "url": url,
                        "raw_content": "",
                        "clean_text": "",
                        "content_hash": "",
                        "is_stale": True,
                        "stale_reason": f"Response too large ({content_length / 1024 / 1024:.1f}MB > 10MB cap)",
                        "status_code": status_code,
                    }

                # Retry on server errors and rate limits
                if status_code in (429, 500, 502, 503, 504) and attempt < max_retries:
                    retry_after = float(response.headers.get("retry-after", 0))
                    wait_time = max(retry_after, 1.0 * (attempt + 1))
                    print(f"[Scraper] HTTP {status_code} for {url}, retrying in {wait_time:.1f}s (attempt {attempt + 1}/{max_retries})...")
                    time.sleep(wait_time)
                    continue

                raw_content = response.text

                # Auto-detect content type and extract clean text
                content_type = _detect_content_type(response)
                clean_text = _extract_text_by_content_type(response, content_type)

                is_stale, stale_reason = check_is_stale(raw_content, clean_text, status_code)
                content_hash = compute_content_hash(clean_text)

                return {
                    "url": url,
                    "raw_content": raw_content,
                    "clean_text": clean_text,
                    "content_hash": content_hash,
                    "is_stale": is_stale,
                    "stale_reason": stale_reason,
                    "status_code": status_code,
                    "content_type": content_type,
                }

        except httpx.ConnectError as exc:
            last_error = exc
            # SSL errors: retry once without strict verification
            if "SSL" in str(exc) or "certificate" in str(exc).lower():
                if verify_ssl:
                    print(f"[Scraper] SSL error for {url}, retrying without strict SSL verification...")
                    verify_ssl = False
                    continue
            # Connection refused / DNS failure: no point retrying immediately
            if attempt < max_retries:
                time.sleep(1.0 * (attempt + 1))
                continue

        except httpx.TimeoutException as exc:
            last_error = exc
            if attempt < max_retries:
                # Increase timeout on retry
                timeout_sec = min(timeout_sec * 1.5, 20.0)
                print(f"[Scraper] Timeout for {url}, retrying with {timeout_sec:.0f}s timeout (attempt {attempt + 1}/{max_retries})...")
                continue

        except httpx.TooManyRedirects as exc:
            last_error = exc
            break  # No point retrying redirect loops

        except Exception as exc:
            last_error = exc
            if attempt < max_retries:
                time.sleep(1.0 * (attempt + 1))
                continue

    # All retries exhausted
    return {
        "url": url,
        "raw_content": "",
        "clean_text": "",
        "content_hash": "",
        "is_stale": True,
        "stale_reason": f"Failed after {max_retries + 1} attempts: {type(last_error).__name__}: {str(last_error)[:200]}",
        "status_code": 0,
    }


async def scrape_url_async(url: str, timeout_sec: float = 10.0) -> Dict[str, Any]:
    """Asynchronous wrapper for scrape_url."""
    return scrape_url(url, timeout_sec=timeout_sec)
