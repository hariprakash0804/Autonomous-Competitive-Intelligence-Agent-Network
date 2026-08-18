import pytest
from app.services.sentiment import sentiment_score, _is_valid_topic_word


def test_positive_sentiment_score():
    positive_text = "This product is incredibly fast, intuitive, and delivers outstanding customer satisfaction."
    result = sentiment_score(positive_text)
    assert result["score"] > 0.3
    assert result["sentiment_category"] == "positive"
    assert "score" in result
    assert isinstance(result["topics"], list)


def test_negative_sentiment_score():
    negative_text = "The platform is terribly slow, constantly crashing, and customer support is awful and unresponsive."
    result = sentiment_score(negative_text)
    assert result["score"] < -0.3
    assert result["sentiment_category"] == "negative"


def test_topic_word_validation():
    # Valid words
    assert _is_valid_topic_word("pricing") is True
    assert _is_valid_topic_word("security") is True
    assert _is_valid_topic_word("api") is True

    # Invalid obfuscated minified tokens or noise
    assert _is_valid_topic_word("xx") is False
    assert _is_valid_topic_word("qj") is False
    assert _is_valid_topic_word("123") is False
