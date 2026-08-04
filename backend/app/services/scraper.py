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


def _ensure_scheme(url: str) -> str:
    """Ensures a URL has an http(s) scheme. Prevents urlparse from returning empty netloc."""
    if not url:
        return url
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    return url


def _get_random_ua() -> str:
    """Returns a random realistic browser User-Agent."""
    return random.choice(USER_AGENTS)


def _build_browser_headers(url: str) -> Dict[str, str]:
    """
    Builds a full set of browser-like headers tailored to the target domain.
    This dramatically reduces bot detection compared to a bare User-Agent.
    """
    url = _ensure_scheme(url)
    parsed = urlparse(url)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    ua = _get_random_ua()

    headers = {
        "User-Agent": ua,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/json,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate",
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

        # SSRF Protection: Block access to localhost, loopback, and private internal IP spaces
        domain_lower = parsed.netloc.split(":")[0].lower()
        # Also check raw URL for IPv6 loopback since urlparse may not parse ::1 into netloc
        raw_lower = url.lower()
        if domain_lower in ("localhost", "127.0.0.1", "0.0.0.0", "::1") or domain_lower.endswith(".local"):
            return False, "Access to localhost or loopback target addresses is forbidden (SSRF Block)"
        if "//::1" in raw_lower or "//[::1]" in raw_lower:
            return False, "Access to localhost or loopback target addresses is forbidden (SSRF Block)"

        # Full RFC 1918 private range check using ipaddress module
        import ipaddress
        try:
            ip = ipaddress.ip_address(domain_lower)
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                return False, "Access to private/reserved IP ranges is forbidden (SSRF Block)"
        except ValueError:
            # Not a raw IP address — it's a hostname, which is fine
            pass

        return True, url
    except Exception as e:
        return False, f"URL parse error: {e}"


def _detect_content_type(response: httpx.Response) -> str:
    """Detects the content type from response headers and binary bytes. Returns: 'html', 'json', 'xml', 'text', or 'binary'."""
    ct = (response.headers.get("content-type") or "").lower()

    # Check for explicit binary MIME types
    if any(b in ct for b in ["application/pdf", "application/zip", "application/octet-stream", "image/", "video/", "audio/", "font/"]):
        return "binary"

    # Check raw content bytes for GZIP magic header (\x1f\x8b), PDF (%PDF), or null bytes
    try:
        content_bytes = response.content[:500]
        if content_bytes.startswith(b"\x1f\x8b") or content_bytes.startswith(b"%PDF") or b"\x00" in content_bytes:
            return "binary"
    except Exception:
        pass

    if "html" in ct:
        return "html"
    elif "json" in ct:
        return "json"
    elif "xml" in ct or "rss" in ct or "atom" in ct:
        return "xml"
    elif "text/" in ct:
        return "text"
    else:
        # Fallback: try to detect from content text safely
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


def _parse_html(html_content: str) -> Optional[BeautifulSoup]:
    """Safely parses HTML into a BeautifulSoup tree. Returns None on failure."""
    if not html_content:
        return None
    try:
        return BeautifulSoup(html_content, "lxml")
    except Exception:
        try:
            return BeautifulSoup(html_content, "html.parser")
        except Exception:
            return None


def clean_html(html_content: str) -> str:
    """
    Extracts visible text content from HTML while preserving text from
    structural elements (header, footer, nav, buttons) that carry company
    identity, contact info, and CTA signals.
    Only strips elements that never contain useful readable text.
    """
    if not html_content:
        return ""
    soup = _parse_html(html_content)
    if soup is None:
        return ""

    # Strip elements that NEVER contain useful readable text.
    # Keep: header, footer, nav (company name, tagline, contact, social links)
    # Keep: button (CTA text like "Start Free Trial", "Book a Demo")
    # Keep: form labels (contact form fields reveal product capabilities)
    for tag in soup([
        "script", "style", "noscript", "svg", "iframe", "template",
        "code", "pre", "symbol", "canvas", "object", "embed",
        "link", "meta",
    ]):
        tag.decompose()

    text = soup.get_text(separator=" ", strip=True)

    # Strip residual inline JSON, JS variable declarations, and CSS rules
    text = re.sub(r"\{\s*\"[^\"]+\"\s*:\s*[^}]+\}", " ", text)
    text = re.sub(r"\b(?:var|const|let)\s+[a-zA-Z0-9_$]+\s*=\s*[^;]+;", " ", text)
    text = re.sub(r"\bfunction\s*\([^)]*\)\s*\{[^}]*\}", " ", text)
    text = re.sub(r"\.[a-zA-Z0-9_-]+\s*\{[^}]*\}", " ", text)
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


# ── Social media domain patterns ─────────────────────────────────────────────
_SOCIAL_DOMAINS = {
    "linkedin": ["linkedin.com"],
    "twitter": ["twitter.com", "x.com"],
    "facebook": ["facebook.com", "fb.com"],
    "instagram": ["instagram.com"],
    "youtube": ["youtube.com", "youtu.be"],
    "github": ["github.com"],
    "discord": ["discord.gg", "discord.com"],
    "slack": ["slack.com"],
    "tiktok": ["tiktok.com"],
    "reddit": ["reddit.com"],
    "crunchbase": ["crunchbase.com"],
}


def extract_structured_metadata(soup: BeautifulSoup, url: str) -> Dict[str, Any]:
    """
    Extracts structured metadata from HTML:
    - <title>, <meta description>, <meta keywords>
    - Open Graph tags (og:title, og:description, og:image, og:site_name, og:type)
    - Twitter Card tags
    - JSON-LD / schema.org structured data
    - Canonical URL
    """
    meta = {
        "title": "",
        "description": "",
        "keywords": [],
        "og_title": "",
        "og_description": "",
        "og_image": "",
        "og_site_name": "",
        "og_type": "",
        "twitter_title": "",
        "twitter_description": "",
        "twitter_image": "",
        "jsonld": [],
        "canonical_url": "",
    }

    # <title>
    title_tag = soup.find("title")
    if title_tag and title_tag.string:
        meta["title"] = title_tag.string.strip()

    # <meta name="description">
    desc_tag = soup.find("meta", attrs={"name": re.compile(r"^description$", re.I)})
    if desc_tag and desc_tag.get("content"):
        meta["description"] = desc_tag["content"].strip()

    # <meta name="keywords">
    kw_tag = soup.find("meta", attrs={"name": re.compile(r"^keywords$", re.I)})
    if kw_tag and kw_tag.get("content"):
        meta["keywords"] = [k.strip() for k in kw_tag["content"].split(",") if k.strip()]

    # Open Graph tags
    og_mappings = {
        "og:title": "og_title",
        "og:description": "og_description",
        "og:image": "og_image",
        "og:site_name": "og_site_name",
        "og:type": "og_type",
    }
    for og_prop, key in og_mappings.items():
        og_tag = soup.find("meta", attrs={"property": og_prop})
        if og_tag and og_tag.get("content"):
            meta[key] = og_tag["content"].strip()

    # Twitter Card tags
    tw_mappings = {
        "twitter:title": "twitter_title",
        "twitter:description": "twitter_description",
        "twitter:image": "twitter_image",
    }
    for tw_name, key in tw_mappings.items():
        tw_tag = soup.find("meta", attrs={"name": tw_name}) or soup.find("meta", attrs={"property": tw_name})
        if tw_tag and tw_tag.get("content"):
            meta[key] = tw_tag["content"].strip()

    # JSON-LD structured data (schema.org)
    for ld_script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            ld_text = ld_script.string or ld_script.get_text()
            if ld_text:
                ld_data = json.loads(ld_text)
                # Normalize to list
                if isinstance(ld_data, dict):
                    meta["jsonld"].append(ld_data)
                elif isinstance(ld_data, list):
                    meta["jsonld"].extend(ld_data)
        except (json.JSONDecodeError, TypeError):
            pass

    # Canonical URL
    canon_tag = soup.find("link", attrs={"rel": "canonical"})
    if canon_tag and canon_tag.get("href"):
        meta["canonical_url"] = urljoin(url, canon_tag["href"].strip())

    return meta


def extract_headings(soup: BeautifulSoup) -> List[Dict[str, Any]]:
    """
    Extracts all heading tags (h1–h6) preserving their hierarchy.
    Captures company tagline (h1), section titles, feature categories, etc.
    Returns [{"level": 1, "text": "..."}, ...]
    """
    headings = []
    for level in range(1, 7):
        for tag in soup.find_all(f"h{level}"):
            text = tag.get_text(separator=" ", strip=True)
            if text and len(text) > 1:
                headings.append({"level": level, "text": text})
    # Sort by document order (find_all returns in order per level, re-sort by position)
    # Re-scan in document order for accuracy
    headings_ordered = []
    for tag in soup.find_all(re.compile(r"^h[1-6]$")):
        text = tag.get_text(separator=" ", strip=True)
        if text and len(text) > 1:
            level = int(tag.name[1])
            headings_ordered.append({"level": level, "text": text})
    return headings_ordered


def extract_social_links(soup: BeautifulSoup, base_url: str) -> Dict[str, str]:
    """
    Scans all <a> tags for social media and contact links.
    Returns {"linkedin": "https://...", "twitter": "https://...", "email": "...", "phone": "...", ...}
    """
    social = {}
    email = ""
    phone = ""

    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"].strip()

        # Email
        if href.startswith("mailto:") and not email:
            email = href.replace("mailto:", "").split("?")[0].strip()
            continue

        # Phone
        if href.startswith("tel:") and not phone:
            phone = href.replace("tel:", "").strip()
            continue

        # Social platforms
        href_lower = href.lower()
        for platform, domains in _SOCIAL_DOMAINS.items():
            if platform not in social:
                for domain in domains:
                    if domain in href_lower:
                        social[platform] = href
                        break

    if email:
        social["email"] = email
    if phone:
        social["phone"] = phone

    return social


def extract_key_images(soup: BeautifulSoup, base_url: str, max_images: int = 10) -> List[Dict[str, str]]:
    """
    Extracts key images with meaningful alt text:
    - Logo (from header, og:image, link[rel=icon])
    - Hero and feature images with descriptive alt text
    Returns [{"src": "...", "alt": "...", "context": "logo|hero|feature"}, ...]
    """
    images = []
    seen_srcs = set()

    def _add_image(src: str, alt: str, context: str):
        if not src or src in seen_srcs or len(images) >= max_images:
            return
        # Skip data URIs, tracking pixels, and tiny spacer images
        if src.startswith("data:") or "pixel" in src.lower() or "spacer" in src.lower():
            return
        full_src = urljoin(base_url, src)
        seen_srcs.add(src)
        images.append({"src": full_src, "alt": alt.strip(), "context": context})

    # 1. Favicon / apple-touch-icon
    for icon_link in soup.find_all("link", attrs={"rel": re.compile(r"icon|apple-touch", re.I)}):
        if icon_link.get("href"):
            _add_image(icon_link["href"], "favicon", "logo")
            break

    # 2. Logo inside <header>
    header = soup.find("header")
    if header:
        header_img = header.find("img")
        if header_img and header_img.get("src"):
            _add_image(header_img["src"], header_img.get("alt", "logo"), "logo")

    # 3. OG image (already in metadata, but also listed here for completeness)
    og_img = soup.find("meta", attrs={"property": "og:image"})
    if og_img and og_img.get("content"):
        _add_image(og_img["content"], "og:image", "hero")

    # 4. Body images with meaningful alt text (skip decorative/empty-alt images)
    for img in soup.find_all("img", src=True):
        alt = img.get("alt", "").strip()
        if alt and len(alt) > 3 and not alt.lower().startswith(("icon", "arrow", "dot", "line")):
            _add_image(img["src"], alt, "feature")

    return images


def extract_cta_signals(soup: BeautifulSoup) -> List[str]:
    """
    Extracts Call-To-Action text from buttons and prominent links.
    Captures signals like "Start Free Trial", "Book a Demo", "Contact Sales", etc.
    """
    cta_texts = []
    seen = set()

    # CTA keyword patterns to filter for genuinely informative CTAs
    cta_keywords = re.compile(
        r"(start|try|get|sign|log|register|subscribe|book|schedule|request|contact|"
        r"download|upgrade|buy|order|free|demo|trial|pricing|plan|quote|learn more|"
        r"see .* in action|watch|explore|compare|join)",
        re.IGNORECASE,
    )

    # 1. <button> elements
    for btn in soup.find_all("button"):
        text = btn.get_text(separator=" ", strip=True)
        if text and len(text) > 2 and len(text) < 80 and text.lower() not in seen:
            if cta_keywords.search(text):
                seen.add(text.lower())
                cta_texts.append(text)

    # 2. <a> elements with CTA-like classes or text
    for a_tag in soup.find_all("a"):
        text = a_tag.get_text(separator=" ", strip=True)
        css_class = " ".join(a_tag.get("class", [])).lower()
        is_cta_class = any(kw in css_class for kw in ["btn", "button", "cta", "action", "hero"])

        if text and len(text) > 2 and len(text) < 80 and text.lower() not in seen:
            if is_cta_class or cta_keywords.search(text):
                seen.add(text.lower())
                cta_texts.append(text)

    # 3. <input type="submit"> values
    for inp in soup.find_all("input", attrs={"type": "submit"}):
        val = inp.get("value", "").strip()
        if val and len(val) > 2 and val.lower() not in seen:
            seen.add(val.lower())
            cta_texts.append(val)

    return cta_texts[:20]  # Cap at 20


# ── Key internal sub-page discovery patterns (Comprehensive SaaS & B2B Web Taxonomy) ──
_KEY_LINK_CATEGORIES = {
    "pricing": [
        r"pricing", r"plans?", r"tiers?", r"costs?", r"billing", r"packages", r"subscriptions?",
        r"quote", r"calculator", r"pricing-plans", r"rate-limits?", r"token-pricing", r"api-pricing",
        r"pay-as-you-go", r"rates", r"usage-pricing", r"pricing-options", r"compare-plans"
    ],
    "features": [
        r"features?", r"products?", r"platform", r"solutions?", r"use-cases?", r"capabilities",
        r"integrations?", r"marketplace", r"ecosystem", r"apps?", r"plugins?", r"technology", r"services?",
        r"models", r"llms", r"inference", r"specs", r"benchmarks", r"architecture", r"tokens"
    ],
    "enterprise": [
        r"enterprise", r"security", r"trust", r"compliance", r"soc2", r"privacy", r"governance",
        r"security-portal", r"hipaa", r"gdpr"
    ],
    "about": [
        r"about", r"company", r"team", r"who-we-are", r"story", r"leadership", r"careers", r"jobs",
        r"culture", r"overview", r"about-us", r"our-mission", r"manifesto", r"investors", r"contact"
    ],
    "docs": [
        r"docs?", r"documentation", r"api", r"developers?", r"help", r"support", r"kb",
        r"knowledge-base", r"guides?", r"tutorials?", r"references?", r"api-reference", r"quickstart", r"sdk"
    ],
    "reviews": [
        r"customers?", r"case-studies", r"testimonials?", r"reviews?", r"stories", r"clients?",
        r"compare", r"versus", r"vs", r"alternatives?", r"customer-stories", r"benchmarks", r"evals", r"leaderboard"
    ],
    "news": [
        r"blog", r"news", r"press", r"updates?", r"changelog", r"resources?", r"events?", r"webinars?",
        r"announcements", r"release-notes", r"releases", r"whats-new"
    ],
}


# ── Comprehensive Pricing Page URL Probing ────────────────────────────────────

# Standard pricing path patterns used by SaaS/tech companies worldwide.
# Ordered by frequency/likelihood — most common patterns first.
_STANDARD_PRICING_PATHS = [
    # Tier 1: Universal patterns (95%+ of SaaS companies)
    "/pricing",
    "/plans",
    "/rates",
    "/api-pricing",
    # Tier 2: Generic product-segment & developer patterns
    "/api/pricing",
    "/pricing/api",
    "/business/pricing",
    "/platform/pricing",
    "/cloud/pricing",
    "/models/pricing",
    # Tier 3: Developer/Enterprise pricing
    "/developers/pricing",
    "/enterprise/pricing",
    "/enterprise",
    "/business",
    "/pro",
    # Tier 4: Alternative naming patterns
    "/pricing-plans",
    "/compare-plans",
    "/pricing-options",
    "/product/pricing",
    "/usage-pricing",
    "/pay-as-you-go",
    # Tier 5: Cost calculators & usage-based pricing
    "/cost",
    "/calculator",
    "/pricing/calculator",
]


def generate_pricing_probe_urls(
    base_url: str,
    homepage_text: str = "",
    max_probes: int = 8,
) -> List[str]:
    """
    Generates a comprehensive list of pricing page URLs to probe for a given domain.

    Many companies hide pricing at non-obvious URLs:
      - OpenAI: /chatgpt/pricing, /api/pricing, /business/pricing
      - Databricks: /product/pricing
      - Snowflake: /pricing-options
      - Anthropic: /pricing (redirects to claude.com/pricing)
      - Google Cloud: /pricing, /products/pricing

    This function generates both static probe paths and dynamic product-specific
    pricing URLs extracted from the homepage content.

    Args:
        base_url: The competitor's seed URL (e.g., "https://openai.com")
        homepage_text: Optional clean text from the homepage to extract product names
        max_probes: Maximum number of probe URLs to return
    Returns:
        List of unique pricing URLs to probe
    """
    base_url = _ensure_scheme(base_url)
    parsed = urlparse(base_url)
    if not parsed.netloc:
        return []
    domain_key = f"{parsed.scheme}://{parsed.netloc}"

    probes = []
    seen = set()

    def _add_probe(path: str):
        url = domain_key + path
        clean = url.rstrip("/")
        if clean not in seen:
            seen.add(clean)
            probes.append(url)

    # ─── Step 1: Extract dynamic product slugs from homepage FIRST ───
    #     so we can interleave them at the right priority level.
    dynamic_slug_probes = []
    if homepage_text:
        extracted_slugs = set()
        _STOP_SLUGS = {
            "the", "our", "new", "all", "and", "for", "get", "see", "try", "log",
            "sign", "contact", "learn", "read", "view", "start", "join", "help",
            "home", "about", "blog", "news", "docs", "team", "more", "here",
            "research", "company", "careers", "jobs", "press", "resources",
            "legal", "privacy", "terms", "security", "trust", "status",
            "partners", "events", "webinars", "changelog", "updates",
        }
        _ALREADY_COVERED = {
            "pricing", "plans", "api", "enterprise", "business", "developers",
            "platform", "cloud", "products", "solutions", "services", "features",
            "support", "console", "dashboard", "account", "settings", "customer-stories",
            "case-studies", "testimonials", "customers", "stories", "intl",
        }

        # Pattern 1: "Try X", "Explore X", "Meet X", "Introducing X"
        for m in re.finditer(r"(?:try|explore|meet|introducing|launch)\s+([A-Z][a-z]+(?:\s[A-Z][a-z]+)?)", homepage_text[:5000]):
            slug = m.group(1).strip().lower().replace(" ", "-")
            if len(slug) >= 3 and slug not in _STOP_SLUGS and slug not in _ALREADY_COVERED:
                extracted_slugs.add(slug)

        # Pattern 2: Markdown links [Product Name](/product/...) from Jina Reader output
        for m in re.finditer(r"\[([A-Za-z][A-Za-z0-9 ]{1,20})\]\((/[a-z][a-z0-9-]*)", homepage_text[:8000]):
            path_slug = m.group(2).strip("/").split("/")[0]
            if len(path_slug) >= 3 and path_slug not in _STOP_SLUGS and path_slug not in _ALREADY_COVERED:
                extracted_slugs.add(path_slug)

        # Pattern 3: Extract from internal URL paths like /chatgpt/, /claude/, /groqcloud/
        for m in re.finditer(r"https?://[^/]+/([a-z][a-z0-9-]{2,15})(?:/|$|\s)", homepage_text[:8000]):
            path_slug = m.group(1)
            if path_slug not in _STOP_SLUGS and path_slug not in _ALREADY_COVERED:
                extracted_slugs.add(path_slug)

        dynamic_slug_probes = [f"/{slug}/pricing" for slug in list(extracted_slugs)[:5]]

    # ─── Step 2: Build prioritized probe list ───
    # Tier 1: Universal patterns (highest priority — always first)
    _add_probe("/pricing")
    _add_probe("/plans")

    # Tier 2: Generic product-segment patterns
    _add_probe("/api/pricing")
    _add_probe("/business/pricing")

    # Tier 2.5: Dynamic product-specific paths (e.g., /chatgpt/pricing, /claude/pricing)
    #           These are HIGH priority because they are tailored to the actual competitor.
    for path in dynamic_slug_probes:
        _add_probe(path)

    # Tier 3: More generic segment patterns
    _add_probe("/platform/pricing")
    _add_probe("/cloud/pricing")
    _add_probe("/developers/pricing")
    _add_probe("/enterprise/pricing")
    _add_probe("/enterprise")

    # Tier 4: Alternative naming patterns (less common)
    _add_probe("/pricing-plans")
    _add_probe("/compare-plans")
    _add_probe("/pricing-options")
    _add_probe("/product/pricing")

    # Tier 5: Cost calculators & usage-based pricing
    _add_probe("/cost")
    _add_probe("/calculator")
    _add_probe("/pricing/calculator")

    # Return capped results, prioritized by tier
    return probes[:max_probes]

def extract_key_internal_links(soup: BeautifulSoup, base_url: str, max_links_per_category: int = 2) -> List[Dict[str, str]]:
    """
    Scans HTML <a> tags and discovers key internal sub-page URLs on the same domain.
    Categorizes discovered links into pricing, features, about, docs, reviews, news.
    Returns a list of dicts: [{"url": "https://...", "category": "pricing", "anchor_text": "..."}, ...]
    """
    discovered = []
    seen_urls = set()

    base_url = _ensure_scheme(base_url)
    parsed_base = urlparse(base_url)
    base_domain = parsed_base.netloc.lower()

    if not base_domain:
        return []

    category_counts = {cat: 0 for cat in _KEY_LINK_CATEGORIES}

    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"].strip()
        if not href or href.startswith(("#", "javascript:", "mailto:", "tel:", "data:")):
            continue

        # Resolve relative URL to absolute URL
        full_url = urljoin(base_url, href)
        parsed_target = urlparse(full_url)

        # Enforce same root domain
        target_domain = parsed_target.netloc.lower()
        if not target_domain or (target_domain != base_domain and not target_domain.endswith("." + base_domain)):
            continue

        # Strip fragments/query params for clean page URL comparison
        clean_target_url = f"{parsed_target.scheme}://{parsed_target.netloc}{parsed_target.path.rstrip('/')}"
        if not parsed_target.path or parsed_target.path == "/":
            clean_target_url = f"{parsed_target.scheme}://{parsed_target.netloc}/"

        # Ignore media/binary/static asset URLs (e.g. .mp4, .jpg, .pdf, .zip)
        path_lower = parsed_target.path.lower()
        if path_lower.endswith((
            ".mp4", ".mp3", ".wav", ".avi", ".mov", ".wmv", ".flv", ".mkv", ".webm",
            ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".ico", ".tiff", ".bmp",
            ".pdf", ".zip", ".tar", ".gz", ".7z", ".rar", ".exe", ".dmg", ".pkg",
            ".css", ".js", ".json", ".xml", ".woff", ".woff2", ".ttf", ".eot"
        )):
            continue

        if clean_target_url in seen_urls or clean_target_url.rstrip("/") == base_url.rstrip("/"):
            continue

        anchor_text = a_tag.get_text(separator=" ", strip=True)
        path_and_anchor = f"{parsed_target.path} {anchor_text}".lower()

        # Check matching category
        for cat, patterns in _KEY_LINK_CATEGORIES.items():
            if category_counts[cat] >= max_links_per_category:
                continue

            for pattern in patterns:
                if re.search(r"\b" + pattern + r"\b", path_and_anchor) or pattern in parsed_target.path.lower():
                    seen_urls.add(clean_target_url)
                    category_counts[cat] += 1
                    discovered.append({
                        "url": clean_target_url,
                        "category": cat,
                        "anchor_text": anchor_text[:60],
                    })
                    break
            if clean_target_url in seen_urls:
                break

    return discovered


# ── Technographic / Tech Stack Signatures ────────────────────────────────────
_TECH_SIGNATURES = {
    "Stripe": [r"stripe\.com", r"stripe-js", r"js\.stripe\.com"],
    "HubSpot": [r"hs-scripts", r"hubspot\.com", r"hs-analytics"],
    "Google Analytics / GA4": [r"googletagmanager", r"google-analytics", r"gtag"],
    "Segment": [r"cdn\.segment\.com", r"analytics\.js"],
    "Intercom": [r"widget\.intercom\.io", r"intercomSettings"],
    "Drift": [r"driftt\.com", r"js\.driftt\.com"],
    "Hotjar": [r"static\.hotjar\.com", r"hj\("],
    "Mixpanel": [r"cdn\.mxpnl\.com", r"mixpanel"],
    "Webflow": [r"webflow\.css", r"w-custom-widget", r"webflow\.com"],
    "WordPress": [r"wp-content", r"wp-includes"],
    "React": [r"react\.production\.min", r"_reactListening", r"data-reactroot"],
    "Next.js": [r"/_next/static", r"__NEXT_DATA__"],
    "Vue.js": [r"vue\.min\.js", r"data-v-"],
    "Shopify": [r"cdn\.shopify\.com", r"Shopify\.theme"],
    "TailwindCSS": [r"tailwind", r"tw-"],
    "Cloudflare": [r"cloudflare", r"cf-ray"],
    "Zendesk": [r"static\.zdassets\.com", r"zendesk"],
}


def extract_tables(soup: BeautifulSoup) -> List[str]:
    """
    Converts HTML <table> elements into formatted Markdown tables.
    Preserves pricing feature comparison matrices and tier comparison tables.
    """
    markdown_tables = []
    for table in soup.find_all("table")[:5]:
        rows = []
        for tr in table.find_all("tr"):
            cells = [td.get_text(separator=" ", strip=True) for td in tr.find_all(["th", "td"])]
            if cells:
                rows.append(cells)
        if not rows or len(rows) < 2:
            continue
        col_count = max(len(r) for r in rows)
        rows = [r + [""] * (col_count - len(r)) for r in rows]

        header = "| " + " | ".join(rows[0]) + " |"
        separator = "| " + " | ".join(["---"] * col_count) + " |"
        body = ["| " + " | ".join(r) + " |" for r in rows[1:]]
        md_table = "\n".join([header, separator] + body)
        markdown_tables.append(md_table)
    return markdown_tables


def extract_faqs(soup: BeautifulSoup) -> List[Dict[str, str]]:
    """
    Extracts Question & Answer pairs from <details><summary> tags and FAQPage JSON-LD schema.
    """
    faqs = []
    # 1. HTML <details><summary>
    for details in soup.find_all("details"):
        summary = details.find("summary")
        if summary:
            q = summary.get_text(strip=True)
            ans = details.get_text(strip=True).replace(q, "").strip()
            if q and ans:
                faqs.append({"question": q, "answer": ans[:300]})

    # 2. JSON-LD FAQPage schema
    for ld in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            data = json.loads(ld.string or ld.get_text() or "{}")
            if isinstance(data, dict) and data.get("@type") == "FAQPage":
                for item in data.get("mainEntity", []):
                    q = item.get("name", "")
                    a = item.get("acceptedAnswer", {}).get("text", "")
                    if q and a:
                        faqs.append({"question": q, "answer": BeautifulSoup(a, "html.parser").get_text(strip=True)[:300]})
        except Exception:
            pass
    return faqs[:10]


def extract_tech_stack(raw_html: str) -> List[str]:
    """
    Detects technographic signatures (Stripe, HubSpot, React, Next.js, Segment, Intercom, etc.)
    from raw HTML script tags, link tags, and meta tags.
    """
    detected = []
    lower_html = raw_html.lower() if raw_html else ""
    for tech, patterns in _TECH_SIGNATURES.items():
        for p in patterns:
            if re.search(p, lower_html, re.I):
                detected.append(tech)
                break
    return detected


def extract_all_structured_data(html_content: str, url: str) -> Dict[str, Any]:
    """
    Master extraction function that runs all structured extractors on raw HTML.
    Returns a dict with keys: metadata, headings, social_links, key_images, cta_signals,
    key_internal_links, markdown_tables, faqs, tech_stack.
    For non-HTML content, returns empty defaults.
    """
    empty = {
        "metadata": {
            "title": "", "description": "", "keywords": [],
            "og_title": "", "og_description": "", "og_image": "",
            "og_site_name": "", "og_type": "",
            "twitter_title": "", "twitter_description": "", "twitter_image": "",
            "jsonld": [], "canonical_url": "",
        },
        "headings": [],
        "social_links": {},
        "key_images": [],
        "cta_signals": [],
        "key_internal_links": [],
        "markdown_tables": [],
        "faqs": [],
        "tech_stack": [],
    }

    if not html_content:
        return empty

    soup = _parse_html(html_content)
    if soup is None:
        return empty

    try:
        return {
            "metadata": extract_structured_metadata(soup, url),
            "headings": extract_headings(soup),
            "social_links": extract_social_links(soup, url),
            "key_images": extract_key_images(soup, url),
            "cta_signals": extract_cta_signals(soup),
            "key_internal_links": extract_key_internal_links(soup, url),
            "markdown_tables": extract_tables(soup),
            "faqs": extract_faqs(soup),
            "tech_stack": extract_tech_stack(html_content),
        }
    except Exception as exc:
        print(f"[Scraper] Structured extraction warning: {exc}")
        return empty


def compute_content_hash(text: str) -> str:
    """Returns SHA-256 hash of string content."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def check_is_stale(html: str, clean_text: str, status_code: int) -> Tuple[bool, Optional[str]]:
    """
    Evaluates whether the scraped content is empty, a JS-render shell,
    binary corrupted data, or blocked by bot detection.
    """
    # Accept any 2xx status code, not just exactly 200
    if status_code < 200 or status_code >= 400:
        return True, f"HTTP status {status_code}"

    if not clean_text or len(clean_text) < MIN_CONTENT_LENGTH:
        return True, f"Content length too short ({len(clean_text) if clean_text else 0} chars)"

    # Detect unprintable / binary garbage corruption
    printable_chars = sum(1 for c in clean_text[:2000] if c.isprintable() or c in ("\n", "\r", "\t"))
    if (printable_chars / max(min(len(clean_text), 2000), 1)) < 0.85:
        return True, "Binary or corrupted non-text response"

    lower_text = clean_text.lower()
    lower_html = html.lower() if html else ""

    # Detect 404 / Page Not Found / Broken URL pages
    # Only flag as 404 on SHORT pages (<1500 chars) — long pages that mention '404'
    # in docs/FAQs are legitimate content, not error pages.
    if len(clean_text) < 1500:
        not_found_patterns = [
            r"^#\s*404\b",
            r"\b404\s*-\s*page\s*not\s*found\b",
            r"\bpage\s*not\s*found\b",
            r"\b404\s*error\b",
            r"\b404\s*not\s*found\b",
            r"\bthis\s*page\s*does\s*not\s*exist\b",
            r"\bthe\s*page\s*you\s*are\s*looking\s*for\s*could\s*not\s*be\s*found\b",
            r"\b404:\s*page\s*not\s*found\b"
        ]

        for nf_pat in not_found_patterns:
            if re.search(nf_pat, lower_text, re.MULTILINE):
                return True, f"Detected 404 Not Found error page pattern: '{nf_pat}'"

    for pattern in JS_SHELL_PATTERNS:
        if re.search(pattern, lower_text) or re.search(pattern, lower_html):
            # Only flag as stale if the total content is very short (actual pages may contain these phrases incidentally)
            if len(clean_text) < 500:
                return True, f"Detected JS shell / bot-block pattern: '{pattern}'"

    return False, None


def _extract_text_by_content_type(response: httpx.Response, content_type: str) -> str:
    """Extracts clean text from a response based on its detected content type, safely handling gzip and binary streams."""
    if content_type == "binary":
        # Check if it is GZIP compressed data that can be safely decompressed into text
        try:
            if response.content.startswith(b"\x1f\x8b"):
                import gzip
                decompressed = gzip.decompress(response.content)
                raw_text = decompressed.decode("utf-8", errors="ignore")
                if "<html" in raw_text.lower():
                    return clean_html(raw_text)
                return re.sub(r"\s+", " ", raw_text).strip()[:10000]
        except Exception:
            pass
        return "[Binary file content - Asset skipped for text analysis]"

    try:
        raw_text = response.text
    except Exception:
        raw_text = response.content.decode("utf-8", errors="ignore")

    # Sanity check: filter out garbled binary characters (\ufffd) or un-rendered gzip
    if "\ufffd" in raw_text[:200] or raw_text.startswith("\x1f\x8b"):
        return "[Non-text binary content skipped]"

    if content_type == "html":
        return clean_html(raw_text)
    elif content_type == "json":
        return clean_json_content(raw_text)
    elif content_type == "xml":
        return clean_xml_content(raw_text)
    else:
        # Plain text — clean up whitespace
        return re.sub(r"\s+", " ", raw_text).strip()[:10000]


def scrape_with_playwright(url: str, timeout_sec: float = 4.0) -> Optional[Dict[str, Any]]:
    """
    High-Speed Headless Browser Scraping (Playwright Chromium):
    Renders JavaScript-heavy Single Page Applications (SPAs) with resource blocking
    (aborts heavy images, videos, fonts) for 500% faster rendering.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("[Scraper] Playwright not installed. Skipping headless browser rendering.")
        return None

    try:
        print(f"[Scraper] Launching optimized Playwright Chromium for SPA: {url}")
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent=_get_random_ua(),
                viewport={"width": 1280, "height": 800},
            )
            page = context.new_page()

            # Abort heavy media, image, and font requests to speed up rendering by 5x
            page.route(
                "**/*.{png,jpg,jpeg,gif,svg,webp,mp4,mp3,wav,woff,woff2,ttf,otf}",
                lambda route: route.abort()
            )

            page.goto(url, wait_until="domcontentloaded", timeout=int(timeout_sec * 1000))
            raw_content = page.content()
            browser.close()

            clean_text = clean_html(raw_content)
            if not clean_text or len(clean_text) < MIN_CONTENT_LENGTH:
                return None

            structured = extract_all_structured_data(raw_content, url)
            content_hash = compute_content_hash(clean_text)

            return {
                "url": url,
                "raw_content": raw_content,
                "clean_text": clean_text,
                "content_hash": content_hash,
                "is_stale": False,
                "stale_reason": None,
                "status_code": 200,
                "content_type": "html",
                "scraped_by": "playwright_chromium",
                **structured,
            }
    except Exception as exc:
        err_msg = str(exc)
        if "Executable doesn't exist" in err_msg or "playwright install" in err_msg:
            print("[Scraper] Playwright Chromium browser binary not installed (run 'playwright install chromium'). Falling back to HTTPX.")
        else:
            print(f"[Scraper] Playwright rendering note: {err_msg[:120]}")
        return None


def _extract_markdown_internal_links(markdown_text: str, base_url: str, max_links_per_category: int = 2) -> List[Dict[str, str]]:
    """
    Extracts key internal links from markdown [text](url) format.
    Used when Jina Reader returns markdown instead of HTML, since extract_key_internal_links
    works on BeautifulSoup <a> tags which don't exist in markdown output.
    """
    discovered = []
    seen_urls = set()
    base_url = _ensure_scheme(base_url)
    parsed_base = urlparse(base_url)
    base_domain = parsed_base.netloc.lower()
    if not base_domain:
        return []

    category_counts = {cat: 0 for cat in _KEY_LINK_CATEGORIES}

    # Match markdown links: [anchor text](url)
    md_link_pattern = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")

    for match in md_link_pattern.finditer(markdown_text):
        anchor_text = match.group(1).strip()
        href = match.group(2).strip()

        if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
            continue

        full_url = urljoin(base_url, href)
        parsed_target = urlparse(full_url)
        target_domain = parsed_target.netloc.lower()

        if not target_domain or (target_domain != base_domain and not target_domain.endswith("." + base_domain)):
            continue

        clean_target_url = f"{parsed_target.scheme}://{parsed_target.netloc}{parsed_target.path.rstrip('/')}"
        if not parsed_target.path or parsed_target.path == "/":
            clean_target_url = f"{parsed_target.scheme}://{parsed_target.netloc}/"

        # Ignore media/binary/static asset URLs (e.g. .mp4, .jpg, .pdf, .zip)
        path_lower = parsed_target.path.lower()
        if path_lower.endswith((
            ".mp4", ".mp3", ".wav", ".avi", ".mov", ".wmv", ".flv", ".mkv", ".webm",
            ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".ico", ".tiff", ".bmp",
            ".pdf", ".zip", ".tar", ".gz", ".7z", ".rar", ".exe", ".dmg", ".pkg",
            ".css", ".js", ".json", ".xml", ".woff", ".woff2", ".ttf", ".eot"
        )):
            continue

        if clean_target_url in seen_urls or clean_target_url.rstrip("/") == base_url.rstrip("/"):
            continue

        path_and_anchor = f"{parsed_target.path} {anchor_text}".lower()

        for cat, patterns in _KEY_LINK_CATEGORIES.items():
            if category_counts[cat] >= max_links_per_category:
                continue
            for pattern in patterns:
                if re.search(r"\b" + pattern + r"\b", path_and_anchor) or pattern in parsed_target.path.lower():
                    seen_urls.add(clean_target_url)
                    category_counts[cat] += 1
                    discovered.append({
                        "url": clean_target_url,
                        "category": cat,
                        "anchor_text": anchor_text[:60],
                    })
                    break
            if clean_target_url in seen_urls:
                break

    return discovered


def scrape_with_jina_reader(url: str, timeout_sec: float = 4.0) -> Optional[Dict[str, Any]]:
    """
    High-Reliability Anti-Bot Fallback Engine (Jina AI Reader Proxy):
    Bypasses Cloudflare bot challenges, JS shells, and anti-scraping blocks for any domain.
    Returns clean markdown text, title, and structured metadata without browser overhead.
    """
    _empty_structured = {
        "metadata": {
            "title": "", "description": "", "keywords": [],
            "og_title": "", "og_description": "", "og_image": "",
            "og_site_name": "", "og_type": "",
            "twitter_title": "", "twitter_description": "", "twitter_image": "",
            "jsonld": [], "canonical_url": "",
        },
        "headings": [],
        "social_links": {},
        "key_images": [],
        "cta_signals": [],
        "key_internal_links": [],
        "markdown_tables": [],
        "faqs": [],
        "tech_stack": [],
    }

    try:
        jina_url = f"https://r.jina.ai/{url}"
        print(f"[Scraper] Triggering Jina AI Reader fallback for blocked/stale URL: {url}", flush=True)

        with httpx.Client(timeout=timeout_sec, follow_redirects=True) as client:
            resp = client.get(jina_url, headers={"Accept": "text/plain"})
            if resp.status_code == 200 and resp.text and len(resp.text) > MIN_CONTENT_LENGTH:
                text = resp.text
                title_match = re.search(r"^Title:\s*(.+)$", text, re.MULTILINE)
                title = title_match.group(1).strip() if title_match else ""

                clean_body = text
                if "Markdown Content:" in text:
                    clean_body = text.split("Markdown Content:", 1)[1].strip()

                content_hash = compute_content_hash(clean_body)
                structured = extract_all_structured_data(f"<html><head><title>{title}</title></head><body>{clean_body}</body></html>", url)
                if title:
                    structured["metadata"]["title"] = title

                # Jina returns markdown [text](url) links, not HTML <a> tags.
                # Extract internal links from markdown format for sub-page discovery.
                if not structured.get("key_internal_links"):
                    structured["key_internal_links"] = _extract_markdown_internal_links(clean_body, url)

                # Check if Jina returned a 404 or stale error page
                is_stale, stale_reason = check_is_stale("", clean_body, 200)

                return {
                    "url": url,
                    "raw_content": text,
                    "clean_text": clean_body,
                    "content_hash": content_hash,
                    "is_stale": is_stale,
                    "stale_reason": stale_reason,
                    "status_code": 404 if is_stale else 200,
                    "content_type": "text/markdown",
                    "scraped_by": "jina_reader",
                    **structured,
                }
    except Exception as exc:
        print(f"[Scraper] Jina AI Reader fallback note for {url}: {exc}")
    return None


def _run_concurrent_fallbacks(url: str, use_playwright: bool = True) -> Optional[Dict[str, Any]]:
    """
    Runs Jina AI Reader fallback engine for blocked or JS-shell target URLs.
    Returns clean markdown content without browser automation overhead.
    """
    return scrape_with_jina_reader(url, timeout_sec=4.0)


def scrape_url(url: str, timeout_sec: float = 3.5, max_retries: int = 1, use_playwright: bool = True) -> Dict[str, Any]:
    """
    High-Performance Multi-Engine Hybrid Scraper:
    1. Fast-Path HTTPX Scraper (sub-second performance).
    2. Concurrent Jina + Playwright Fallback (parallel for max speed).
    """
    _empty_structured = {
        "metadata": {
            "title": "", "description": "", "keywords": [],
            "og_title": "", "og_description": "", "og_image": "",
            "og_site_name": "", "og_type": "",
            "twitter_title": "", "twitter_description": "", "twitter_image": "",
            "jsonld": [], "canonical_url": "",
        },
        "headings": [],
        "social_links": {},
        "key_images": [],
        "cta_signals": [],
        "key_internal_links": [],
        "markdown_tables": [],
        "faqs": [],
        "tech_stack": [],
    }

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
            "content_type": "",
            "scraped_by": "none",
            **_empty_structured,
        }
    url = url_or_error

    # 2. Fast-Path Engine: HTTPX Client (sub-second performance)
    last_error = None
    verify_ssl = True
    jina_tried = False  # Track to avoid duplicate Jina calls

    for attempt in range(max_retries + 1):
        headers = _build_browser_headers(url)
        timeout_config = httpx.Timeout(timeout_sec, connect=2.0)

        try:
            with httpx.Client(
                headers=headers,
                follow_redirects=True,
                timeout=timeout_config,
                verify=verify_ssl,
                max_redirects=5,
            ) as client:
                response = client.get(url)
                status_code = response.status_code

                # Check actual response body size (handles servers that don't send content-length)
                content_length = int(response.headers.get("content-length", 0))
                actual_size = len(response.content)
                effective_size = max(content_length, actual_size)
                if effective_size > MAX_RESPONSE_BYTES:
                    return {
                        "url": url,
                        "raw_content": "",
                        "clean_text": "",
                        "content_hash": "",
                        "is_stale": True,
                        "stale_reason": f"Response too large ({effective_size / 1024 / 1024:.1f}MB > 10MB cap)",
                        "status_code": status_code,
                        "content_type": "",
                        "scraped_by": "httpx",
                        **_empty_structured,
                    }

                if status_code in (429, 500, 502, 503, 504) and attempt < max_retries:
                    time.sleep(0.5 * (attempt + 1))
                    continue

                content_type = _detect_content_type(response)
                clean_text = _extract_text_by_content_type(response, content_type)
                raw_content = clean_text if content_type == "binary" else response.text

                if content_type == "html":
                    structured = extract_all_structured_data(raw_content, url)
                else:
                    structured = _empty_structured

                is_stale, stale_reason = check_is_stale(raw_content, clean_text, status_code)
                content_hash = compute_content_hash(clean_text)

                # If fast-path HTTPX succeeded cleanly, return immediately (sub-second execution!)
                if not is_stale:
                    return {
                        "url": url,
                        "raw_content": raw_content,
                        "clean_text": clean_text,
                        "content_hash": content_hash,
                        "is_stale": False,
                        "stale_reason": None,
                        "status_code": status_code,
                        "content_type": content_type,
                        "scraped_by": "httpx",
                        **structured,
                    }

                # Stale content detected — run Jina + Playwright CONCURRENTLY for max speed
                if is_stale:
                    jina_tried = True
                    concurrent_res = _run_concurrent_fallbacks(url, use_playwright=(use_playwright and content_type == "html"))
                    if concurrent_res:
                        return concurrent_res

                return {
                    "url": url,
                    "raw_content": raw_content,
                    "clean_text": clean_text,
                    "content_hash": content_hash,
                    "is_stale": is_stale,
                    "stale_reason": stale_reason,
                    "status_code": status_code,
                    "content_type": content_type,
                    "scraped_by": "httpx",
                    **structured,
                }

        except httpx.ConnectError as exc:
            last_error = exc
            if "SSL" in str(exc) or "certificate" in str(exc).lower():
                if verify_ssl:
                    verify_ssl = False
                    continue
            if attempt < max_retries:
                time.sleep(0.5 * (attempt + 1))
                continue

        except httpx.TimeoutException as exc:
            last_error = exc
            if attempt < max_retries:
                continue

        except Exception as exc:
            last_error = exc
            if attempt < max_retries:
                time.sleep(0.5 * (attempt + 1))
                continue

    # Final fallback: Run concurrent Jina + Playwright ONLY if not already tried
    if not jina_tried:
        concurrent_res = _run_concurrent_fallbacks(url, use_playwright=use_playwright)
        if concurrent_res:
            return concurrent_res

    return {
        "url": url,
        "raw_content": "",
        "clean_text": "",
        "content_hash": "",
        "is_stale": True,
        "stale_reason": f"Failed after {max_retries + 1} attempts: {type(last_error).__name__}: {str(last_error)[:200]}",
        "status_code": 0,
        "content_type": "",
        "scraped_by": "none",
        **_empty_structured,
    }


async def scrape_url_async(url: str, timeout_sec: float = 10.0) -> Dict[str, Any]:
    """Truly asynchronous wrapper — runs scrape_url in a thread pool to avoid blocking the event loop."""
    import asyncio
    return await asyncio.to_thread(scrape_url, url, timeout_sec)
