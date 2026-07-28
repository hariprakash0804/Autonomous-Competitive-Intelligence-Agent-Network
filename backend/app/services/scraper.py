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
        r"quote", r"calculator", r"pricing-plans"
    ],
    "features": [
        r"features?", r"products?", r"platform", r"solutions?", r"use-cases?", r"capabilities",
        r"integrations?", r"marketplace", r"ecosystem", r"apps?", r"plugins?", r"technology", r"services?"
    ],
    "enterprise": [
        r"enterprise", r"security", r"trust", r"compliance", r"soc2", r"privacy", r"governance"
    ],
    "about": [
        r"about", r"company", r"team", r"who-we-are", r"story", r"leadership", r"careers", r"jobs",
        r"culture", r"overview"
    ],
    "docs": [
        r"docs?", r"documentation", r"api", r"developers?", r"help", r"support", r"kb",
        r"knowledge-base", r"guides?", r"tutorials?", r"references?"
    ],
    "reviews": [
        r"customers?", r"case-studies", r"testimonials?", r"reviews?", r"stories", r"clients?",
        r"compare", r"versus", r"vs", r"alternatives?"
    ],
    "news": [
        r"blog", r"news", r"press", r"updates?", r"changelog", r"resources?", r"events?", r"webinars?"
    ],
}


def extract_key_internal_links(soup: BeautifulSoup, base_url: str, max_links_per_category: int = 2) -> List[Dict[str, str]]:
    """
    Scans HTML <a> tags and discovers key internal sub-page URLs on the same domain.
    Categorizes discovered links into pricing, features, about, docs, reviews, news.
    Returns a list of dicts: [{"url": "https://...", "category": "pricing", "anchor_text": "..."}, ...]
    """
    discovered = []
    seen_urls = set()

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


def scrape_with_playwright(url: str, timeout_sec: float = 15.0) -> Optional[Dict[str, Any]]:
    """
    Headless Browser Scraping (Playwright):
    Renders JavaScript-heavy Single Page Applications (SPAs) requiring dynamic client-side DOM rendering
    using headless Playwright Chromium.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("[Scraper] Playwright not installed. Skipping headless browser rendering.")
        return None

    try:
        print(f"[Scraper] Launching Playwright Chromium headless browser for SPA rendering: {url}")
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent=_get_random_ua(),
                viewport={"width": 1280, "height": 800},
            )
            page = context.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=int(timeout_sec * 1000))
            page.wait_for_timeout(1500)
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
            print(f"[Scraper] Playwright headless browser rendering note: {err_msg[:120]}")
        return None


def scrape_url(url: str, timeout_sec: float = 10.0, max_retries: int = 2, use_playwright: bool = True) -> Dict[str, Any]:
    """
    Robust HTTP & Headless Browser Scraper:
    - Static HTML pages, SPAs, API endpoints (JSON), RSS/XML feeds, plain text
    - Dynamic JavaScript-heavy SPA rendering via Playwright Chromium fallback
    - Rotating User-Agents + full browser-like headers to avoid bot detection
    - Automatic retry with backoff on transient failures
    - Content-type auto-detection for HTML/JSON/XML/text
    - Response size cap (10MB) to avoid memory issues
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
            **_empty_structured,
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

                # Extract structured data from HTML pages
                if content_type == "html":
                    structured = extract_all_structured_data(raw_content, url)
                else:
                    structured = _empty_structured

                is_stale, stale_reason = check_is_stale(raw_content, clean_text, status_code)
                content_hash = compute_content_hash(clean_text)

                # If content is flagged as JS shell or empty SPA, attempt Playwright Headless rendering
                if is_stale and use_playwright and content_type == "html":
                    pw_res = scrape_with_playwright(url, timeout_sec=timeout_sec * 1.5)
                    if pw_res and not pw_res.get("is_stale"):
                        return pw_res

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
                    print(f"[Scraper] SSL error for {url}, retrying without strict SSL verification...")
                    verify_ssl = False
                    continue
            if attempt < max_retries:
                time.sleep(1.0 * (attempt + 1))
                continue

        except httpx.TimeoutException as exc:
            last_error = exc
            if attempt < max_retries:
                timeout_sec = min(timeout_sec * 1.5, 20.0)
                print(f"[Scraper] Timeout for {url}, retrying with {timeout_sec:.0f}s timeout (attempt {attempt + 1}/{max_retries})...")
                continue

        except httpx.TooManyRedirects as exc:
            last_error = exc
            break

        except Exception as exc:
            last_error = exc
            if attempt < max_retries:
                time.sleep(1.0 * (attempt + 1))
                continue

    # Attempt Playwright if HTTP attempts failed
    if use_playwright:
        pw_res = scrape_with_playwright(url, timeout_sec=timeout_sec * 1.5)
        if pw_res and not pw_res.get("is_stale"):
            return pw_res

    # All retries exhausted
    return {
        "url": url,
        "raw_content": "",
        "clean_text": "",
        "content_hash": "",
        "is_stale": True,
        "stale_reason": f"Failed after {max_retries + 1} attempts: {type(last_error).__name__}: {str(last_error)[:200]}",
        "status_code": 0,
        **_empty_structured,
    }


async def scrape_url_async(url: str, timeout_sec: float = 10.0) -> Dict[str, Any]:
    """Asynchronous wrapper for scrape_url."""
    return scrape_url(url, timeout_sec=timeout_sec)
