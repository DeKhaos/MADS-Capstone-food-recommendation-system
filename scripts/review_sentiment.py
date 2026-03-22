import re
from typing import List, Optional, Union


POSITIVE_WORDS = {
    "easy", "simple", "quick", "perfect", "great", "excellent", "amazing",
    "delicious", "love", "loved", "fantastic", "wonderful", "best", "good"
}

NEGATIVE_WORDS = {
    "hard", "difficult", "complicated", "bad", "terrible", "awful",
    "confusing", "failed", "messy", "disappointing", "worst", "annoying"
}


def normalize_text(text: str) -> List[str]:
    if not text:
        return []

    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return text.split()


def compute_review_sentiment(reviews: Optional[Union[List[str], str]]) -> dict:
    """
    Returns review sentiment as metadata only.
    Missing reviews do not create a penalty.
    """
    if not reviews:
        return {
            "has_reviews": False,
            "review_sentiment_score": None,
            "review_sentiment_label": None,
        }

    if isinstance(reviews, str):
        reviews = [reviews]

    pos = 0
    neg = 0

    for review in reviews:
        for token in normalize_text(review):
            if token in POSITIVE_WORDS:
                pos += 1
            elif token in NEGATIVE_WORDS:
                neg += 1

    total = pos + neg

    if total == 0:
        score = 0.0
    else:
        score = round((pos - neg) / total, 3)

    if score > 0.2:
        label = "positive"
    elif score < -0.2:
        label = "negative"
    else:
        label = "neutral"

    return {
        "has_reviews": True,
        "review_sentiment_score": score,
        "review_sentiment_label": label,
    }