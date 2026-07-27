import re
import json
from collections import Counter
from typing import Dict, Any, List
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

from app.config import settings

analyzer = SentimentIntensityAnalyzer()

# Expanded English stop words + HTML/CSS/JS code noise terms
STOP_WORDS = {
    # English filler & stop words
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "with",
    "by", "about", "against", "between", "into", "through", "during", "before",
    "after", "above", "below", "from", "up", "down", "out", "off", "over", "under",
    "again", "further", "then", "once", "here", "there", "when", "where", "why",
    "how", "all", "any", "both", "each", "few", "more", "most", "other", "some",
    "such", "no", "nor", "not", "only", "own", "same", "so", "than", "too", "very",
    "can", "will", "just", "should", "now", "was", "were", "have", "has", "had",
    "this", "that", "these", "those", "be", "been", "being", "its", "our", "you",
    "your", "we", "they", "them", "their", "also", "new", "using", "use", "make",
    "made", "get", "got", "see", "seen", "take", "took", "like", "well", "way",
    "may", "must", "might", "could", "would", "shall", "does", "done", "doing",
    "which", "who", "whom", "whose", "what", "where", "when", "why", "how",

    # Web, HTML, CSS, JS, API & minified code noise
    "class", "classname", "style", "styles", "div", "span", "href", "http", "https",
    "www", "com", "org", "net", "var", "let", "const", "function", "return", "null",
    "true", "false", "undefined", "window", "document", "element", "node", "index",
    "value", "type", "name", "data", "id", "text", "content", "page", "site", "link",
    "main", "item", "group", "row", "col", "view", "btn", "button", "svg", "path",
    "fill", "stroke", "display", "block", "none", "hidden", "active", "hover", "focus",
    "transition", "transform", "opacity", "zindex", "align", "justify", "center",
    "top", "bottom", "left", "right", "auto", "inherit", "initial", "unset", "px",
    "rem", "em", "vh", "vw", "max", "min", "width", "height", "script", "noscript",
    "header", "footer", "nav", "iframe", "code", "pre", "menu", "section", "article",
    "body", "head", "meta", "title", "link", "input", "form", "select", "option",
    "label", "textarea", "table", "tbody", "thead", "tr", "td", "th", "ul", "ol",
    "li", "img", "src", "alt", "flex", "grid", "border", "color", "background",
    "margin", "padding", "font", "size", "overflow", "cursor", "pointer", "relative",
    "absolute", "fixed", "sticky", "sans", "serif", "mono", "solid", "dotted", "dashed",
    "rounded", "shadow", "radius", "family", "weight", "bold", "normal", "italic",
    "important", "media", "query", "charset", "import", "export", "default", "module",
    "require", "async", "await", "object", "array", "string", "number", "boolean",
    "promise", "catch", "finally", "throw", "try", "error", "event", "target", "click",
    "change", "submit", "load", "cookie", "cookies", "cache", "token", "session"
}

# Recognized 3-letter technical/business terms allowed as topics
VALID_3_LETTER_WORDS = {
    "api", "app", "web", "dev", "pro", "pay", "tax", "b2b", "cpu", "gpu", "saas",
    "doc", "sdk", "bot", "ai", "ml", "db", "sql", "git", "hub", "log", "run", "opt",
    "cli", "gui", "ops", "sec", "key", "url", "uri", "ip", "dns", "ssl", "tls"
}

VOWELS = set("aeiouy")


# Explicit blacklist for known obfuscated minified JS variable names
BLACKLIST_OBFUSCATED = {"uuow", "exvu", "nrx", "mmnl", "eid", "uuow", "exvu"}

# Regex matching impossible/obfuscated letter combinations in English words
INVALID_PHONOTACTICS = re.compile(
    r"xv|xj|zx|qj|fx|fz|kx|jx|vf|vj|vk|vm|vn|vp|vq|vw|vx|vy|vz|wx|wz|xb|xc|xd|xf|xg|xh|xj|xk|xm|xn|xp|xq|xr|xs|xt|xw|xz|yy|qq|jj|kk|vv|ww|^uu|^q[^u]"
)


def _is_valid_topic_word(word: str) -> bool:
    """
    Validates whether a word is a real, meaningful topic vs minified JS code or gibberish.
    Checks vowel presence, length constraints, repeating patterns, and phonotactic rules.
    """
    w = word.lower().strip()
    if not w or len(w) < 3 or not w.isalpha():
        return False

    if w in BLACKLIST_OBFUSCATED:
        return False

    if len(w) == 3 and w not in VALID_3_LETTER_WORDS:
        return False

    # Must contain at least one vowel
    if not any(char in VOWELS for char in w):
        return False

    # Check for repeating character triples (e.g. 'aaa')
    if re.search(r"(.)\1\1", w):
        return False

    # Check for impossible/minified letter combinations
    if INVALID_PHONOTACTICS.search(w):
        return False

    # Check for 4+ consecutive consonants (minified variable or hash string)
    consonant_cluster = re.search(r"[bcdfghjklmnpqrstvwxz]{4,}", w)
    if consonant_cluster and w not in {"strength", "length"}:
        return False

    return True


def extract_key_topics(text: str, top_n: int = 5) -> List[str]:
    """
    Extracts top non-stopword, meaningful keywords/topics from text.
    Strictly filters out minified JS code, CSS classes, HTML noise, and gibberish.
    """
    if not text:
        return ["overview", "features", "pricing", "platform"]

    words = re.findall(r"\b[a-zA-Z]{3,}\b", text.lower())
    valid_words = [
        w for w in words
        if w not in STOP_WORDS and _is_valid_topic_word(w)
    ]

    counts = Counter(valid_words)
    extracted = [word for word, count in counts.most_common(top_n)]

    # Fallback to sensible defaults if no clean topics could be extracted
    if not extracted:
        return ["overview", "features", "pricing", "platform"]

    return extracted


def _vader_sentiment(text: str) -> Dict[str, Any]:
    """Fast local VADER-based sentiment analysis (no API calls)."""
    if not text or len(text.strip()) == 0:
        return {
            "score": 0.0,
            "topics": [],
            "sentiment_category": "neutral",
            "raw_scores": {"neg": 0.0, "neu": 1.0, "pos": 0.0, "compound": 0.0},
        }

    sample_text = text[:5000]
    scores = analyzer.polarity_scores(sample_text)
    compound = round(scores["compound"], 4)

    if compound >= 0.05:
        category = "positive"
    elif compound <= -0.05:
        category = "negative"
    else:
        category = "neutral"

    topics = extract_key_topics(sample_text, top_n=5)

    return {
        "score": compound,
        "topics": topics,
        "sentiment_category": category,
        "raw_scores": scores,
    }


def _llm_sentiment(text: str) -> Dict[str, Any]:
    """
    LLM-powered deep sentiment analysis using OpenRouter.
    Provides richer topic extraction, nuanced sentiment scoring, and competitive insights.
    Falls back to VADER if LLM is unavailable.
    """
    from app.services.llm import call_openrouter

    api_key = settings.LLM_API_KEY or ""
    if not api_key:
        return _vader_sentiment(text)

    # Truncate to keep prompt size reasonable for free-tier models
    sample_text = text[:3000]

    prompt = f"""Analyze the following competitor content for sentiment and key topics.

CONTENT:
{sample_text}

Respond ONLY with valid JSON in this exact format (no markdown, no extra text):
{{
  "score": <float from -1.0 to 1.0 where -1=very negative, 0=neutral, 1=very positive>,
  "sentiment_category": "<positive|neutral|negative>",
  "topics": ["<topic1>", "<topic2>", "<topic3>", "<topic4>", "<topic5>"],
  "key_insights": "<1-2 sentence summary of the sentiment drivers and competitive positioning>"
}}"""

    try:
        response_text, model_used = call_openrouter(prompt, api_key)
        print(f"[LLM Sentiment] Analysis completed via {model_used}", flush=True)

        # Parse JSON from response (handle potential markdown wrapping)
        json_text = response_text.strip()
        if json_text.startswith("```"):
            json_text = re.sub(r"```(?:json)?\s*", "", json_text)
            json_text = json_text.rstrip("`").strip()

        parsed = json.loads(json_text)

        # Validate and normalize the response
        score = float(parsed.get("score", 0.0))
        score = max(-1.0, min(1.0, score))  # Clamp to [-1, 1]

        category = parsed.get("sentiment_category", "neutral")
        if category not in ("positive", "neutral", "negative"):
            category = "positive" if score >= 0.05 else ("negative" if score <= -0.05 else "neutral")

        topics = parsed.get("topics", [])
        if not isinstance(topics, list):
            topics = extract_key_topics(sample_text, top_n=5)
        topics = [str(t) for t in topics[:8]]  # Cap at 8 topics

        result = {
            "score": round(score, 4),
            "topics": topics,
            "sentiment_category": category,
            "raw_scores": {"compound": score},
            "key_insights": str(parsed.get("key_insights", "")),
            "model_used": model_used,
        }
        return result

    except json.JSONDecodeError as e:
        print(f"[LLM Sentiment] JSON parse failed: {e}. Falling back to VADER.", flush=True)
        return _vader_sentiment(text)
    except Exception as e:
        print(f"[LLM Sentiment] LLM call failed: {e}. Falling back to VADER.", flush=True)
        return _vader_sentiment(text)


def sentiment_score(text: str) -> Dict[str, Any]:
    """
    Smart sentiment analysis that uses LLM when available, VADER as fallback.
    - If LLM_PROVIDER=openrouter and LLM_API_KEY is set → uses LLM for deep analysis
    - Otherwise → uses fast local VADER analysis
    Both return the same interface: {score, topics, sentiment_category, raw_scores}
    """
    provider = (settings.LLM_PROVIDER or "").lower().strip()
    api_key = settings.LLM_API_KEY or ""

    if provider == "openrouter" and api_key:
        return _llm_sentiment(text)

    return _vader_sentiment(text)
