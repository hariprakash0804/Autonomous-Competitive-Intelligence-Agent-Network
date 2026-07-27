import re
import json
from collections import Counter
from typing import Dict, Any, List
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

from app.config import settings

analyzer = SentimentIntensityAnalyzer()

# Common English stop words for quick topic extraction
STOP_WORDS = {
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "with",
    "by", "about", "against", "between", "into", "through", "during", "before",
    "after", "above", "below", "from", "up", "down", "in", "out", "on", "off",
    "over", "under", "again", "further", "then", "once", "here", "there", "when",
    "where", "why", "how", "all", "any", "both", "each", "few", "more", "most",
    "other", "some", "such", "no", "nor", "not", "only", "own", "same", "so",
    "than", "too", "very", "s", "t", "can", "will", "just", "don", "should",
    "now", "is", "was", "are", "were", "have", "has", "had", "this", "that",
    "these", "those", "be", "been", "being", "it", "its", "our", "you", "your",
    "we", "they", "them", "their", "more", "also", "new", "using", "use"
}


def extract_key_topics(text: str, top_n: int = 5) -> List[str]:
    """Extracts top non-stopword keywords/topics from text."""
    words = re.findall(r"\b[a-zA-Z]{3,}\b", text.lower())
    filtered = [w for w in words if w not in STOP_WORDS]
    counts = Counter(filtered)
    return [word for word, _ in counts.most_common(top_n)]


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
