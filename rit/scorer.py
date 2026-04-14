"""
scorer.py — NLP scoring pipeline for review text.

Uses HuggingFace Transformers for sentiment classification and a keyword-based
approach for wellness signal and theme tagging. Models are loaded lazily on
first use to keep import time fast.

Scoring is designed to run in a separate pass from scraping:
  1. Scraper inserts reviews with wellness_signal = NULL.
  2. score_reviews_batch() fetches all unscored reviews, scores them, and
     writes the results back in place.
"""

from __future__ import annotations

import re
from typing import Literal

from supabase import Client
from tqdm import tqdm

# ---------------------------------------------------------------------------
# Theme taxonomy
# ---------------------------------------------------------------------------
THEME_TAXONOMY: list[str] = [
    "ambiance",
    "staff",
    "value",
    "wait_time",
    "cleanliness",
    "results",
    "booking",
    "music",
    "relaxation",
    "pain",
]

# Keyword hints per theme — expand these as you review real data
_THEME_KEYWORDS: dict[str, list[str]] = {
    "ambiance":    ["vibe", "atmosphere", "decor", "environment", "cozy", "aesthetic"],
    "staff":       ["staff", "technician", "therapist", "receptionist", "team", "friendly", "rude", "professional"],
    "value":       ["price", "worth", "expensive", "affordable", "overpriced", "value", "deal"],
    "wait_time":   ["wait", "late", "on time", "appointment", "rushed", "slow", "quick"],
    "cleanliness": ["clean", "dirty", "sanitary", "hygiene", "spotless", "gross"],
    "results":     ["result", "effective", "worked", "improved", "difference", "outcome", "before and after"],
    "booking":     ["book", "cancel", "reschedule", "app", "online", "reservation", "confirm"],
    "music":       ["music", "playlist", "sound", "quiet", "loud", "noise", "audio"],
    "relaxation":  ["relax", "calm", "zen", "peaceful", "stress", "unwind", "meditat"],
    "pain":        ["pain", "hurt", "sore", "tender", "uncomfortable", "gentle", "pressure"],
}

# Wellness-adjacent language — used to compute wellness_signal
_WELLNESS_KEYWORDS: list[str] = [
    "relax", "calm", "stress", "wellness", "heal", "restore", "rejuvenat",
    "therapeutic", "mindful", "meditat", "detox", "glow", "serene", "tranquil",
    "holistic", "energy", "balance", "renewal", "reset", "recover", "float",
    "sauna", "acupuncture", "tension", "breathe", "centered",
]

# ---------------------------------------------------------------------------
# Lazy model loader
# ---------------------------------------------------------------------------
_sentiment_pipeline = None


def _get_sentiment_pipeline():
    """Load the sentiment model once and cache it."""
    global _sentiment_pipeline
    if _sentiment_pipeline is None:
        from transformers import pipeline as hf_pipeline

        # distilbert-base-uncased-finetuned-sst-2-english is fast, ~260 MB
        # TODO: swap for a domain-specific model if accuracy needs improvement
        _sentiment_pipeline = hf_pipeline(
            "sentiment-analysis",
            model="distilbert-base-uncased-finetuned-sst-2-english",
            truncation=True,
            max_length=512,
        )
    return _sentiment_pipeline


# ---------------------------------------------------------------------------
# Public scoring functions
# ---------------------------------------------------------------------------

def score_wellness_signal(text: str) -> float:
    """
    Return a float 0–1 representing how wellness-relevant the review text is.

    Current approach: keyword density (count of wellness keyword matches
    divided by a normalising constant). Simple and fast; replace with an
    embedding-based scorer if you need more precision.
    """
    if not text:
        return 0.0

    lowered = text.lower()
    hits = sum(1 for kw in _WELLNESS_KEYWORDS if kw in lowered)
    # Normalise: 5+ hits → 1.0, scale linearly below that
    return min(hits / 5.0, 1.0)


def classify_sentiment(text: str) -> Literal["positive", "neutral", "negative"]:
    """
    Classify review text as 'positive', 'neutral', or 'negative'.

    Uses a pretrained HuggingFace sentiment model. The model returns POSITIVE
    or NEGATIVE with a confidence score; scores below 0.65 are mapped to
    'neutral' to avoid over-committing on ambiguous text.
    """
    if not text or not text.strip():
        return "neutral"

    pipe = _get_sentiment_pipeline()
    result = pipe(text[:512])[0]  # truncate to model limit

    label: str = result["label"].lower()   # "positive" or "negative"
    score: float = result["score"]

    if score < 0.65:
        return "neutral"
    return label  # type: ignore[return-value]


def extract_theme_tags(text: str) -> list[str]:
    """
    Return the subset of THEME_TAXONOMY found in the review text.

    Uses simple substring matching against per-theme keyword lists.
    TODO: upgrade to zero-shot classification with a model if recall is poor.
    """
    if not text:
        return []

    lowered = text.lower()
    matched: list[str] = []
    for theme, keywords in _THEME_KEYWORDS.items():
        if any(kw in lowered for kw in keywords):
            matched.append(theme)
    return matched


def score_reviews_batch(client: Client, batch_size: int = 100) -> None:
    """
    Fetch all unscored reviews (wellness_signal IS NULL), score them,
    and write results back to the reviews table.

    Processes in batches to avoid loading the entire table into memory.
    """
    offset = 0
    total_scored = 0

    while True:
        # Fetch a batch of unscored reviews
        response = (
            client.table("reviews")
            .select("id, text")
            .is_("wellness_signal", "null")
            .range(offset, offset + batch_size - 1)
            .execute()
        )
        rows = response.data
        if not rows:
            break

        for row in tqdm(rows, desc=f"Scoring batch offset={offset}"):
            text: str = row.get("text") or ""

            wellness = score_wellness_signal(text)
            sentiment = classify_sentiment(text)
            tags = extract_theme_tags(text)

            client.table("reviews").update(
                {
                    "wellness_signal": wellness,
                    "sentiment": sentiment,
                    "theme_tags": tags,
                }
            ).eq("id", row["id"]).execute()

        total_scored += len(rows)
        offset += batch_size

    print(f"Scored {total_scored} review(s).")
