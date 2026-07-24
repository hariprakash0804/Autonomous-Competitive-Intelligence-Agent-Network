import re
from collections import Counter
from typing import Dict, Any, List
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

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


def sentiment_score(text: str) -> Dict[str, Any]:
    """
    Computes VADER sentiment score (-1.0 to 1.0) and extracts key topics.
    Returns:
      {
        "score": float (compound),
        "topics": list[str],
        "sentiment_category": "positive" | "neutral" | "negative",
        "raw_scores": dict
      }
    """
    if not text or len(text.strip()) == 0:
        return {
            "score": 0.0,
            "topics": [],
            "sentiment_category": "neutral",
            "raw_scores": {"neg": 0.0, "neu": 1.0, "pos": 0.0, "compound": 0.0},
        }

    # Truncate text for analysis if excessively long to keep execution fast
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
