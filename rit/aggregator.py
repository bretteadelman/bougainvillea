"""
aggregator.py — ZIP-level summary computation.

Reads from the businesses and reviews tables, computes per-ZIP wellness gap
metrics, and upserts results into zip_summaries.

Wellness gap intuition:
  A high wellness_gap_score means an area has strong wellness-adjacent language
  in its reviews (people want wellness) but relatively few businesses serving
  that need. High signal + low density = opportunity.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Any

from supabase import Client
from tqdm import tqdm


# ---------------------------------------------------------------------------
# Gap statement templates
# ---------------------------------------------------------------------------
# Chosen based on gap score quartile. Swap for AI-generated copy later.
_GAP_TEMPLATES = [
    # Low gap (0.0–0.25)
    "{zip} is well-served by wellness businesses relative to demand.",
    # Moderate gap (0.25–0.50)
    "{zip} shows moderate wellness demand with room for additional providers.",
    # High gap (0.50–0.75)
    "{zip} has clear wellness demand but limited business supply — a growing opportunity.",
    # Very high gap (0.75–1.0)
    "{zip} shows strong unmet wellness demand; the market is significantly underserved.",
]


def _gap_template(zip_code: str, gap_score: float) -> str:
    idx = min(int(gap_score / 0.25), 3)
    return _GAP_TEMPLATES[idx].format(zip=zip_code)


# ---------------------------------------------------------------------------
# Core computation
# ---------------------------------------------------------------------------

def compute_zip_summary(client: Client, zip_code: str) -> dict[str, Any]:
    """
    Aggregate review data for all businesses in zip_code and compute:
      - business_count
      - review_count
      - top_themes   (JSONB: tag → count, top 10)
      - wellness_gap_score
      - gap_statement

    Wellness gap formula:
      avg_wellness_signal = mean of wellness_signal across all scored reviews
      density_factor      = 1 / log10(max(business_count, 2))
                            (fewer businesses → higher multiplier)
      gap_score           = min(avg_wellness_signal * density_factor, 1.0)

    This rewards ZIPs where reviewers use lots of wellness language but there
    are few businesses to meet that demand.
    """
    import math

    # Fetch all businesses in this ZIP
    biz_resp = (
        client.table("businesses")
        .select("id")
        .eq("zip_code", zip_code)
        .execute()
    )
    business_ids = [row["id"] for row in biz_resp.data]
    business_count = len(business_ids)

    if business_count == 0:
        return {
            "zip_code": zip_code,
            "business_count": 0,
            "review_count": 0,
            "top_themes": {},
            "wellness_gap_score": 0.0,
            "gap_statement": f"No businesses found in {zip_code}.",
            "last_computed": datetime.now(timezone.utc).isoformat(),
        }

    # Fetch all scored reviews for those businesses
    reviews_resp = (
        client.table("reviews")
        .select("wellness_signal, theme_tags")
        .in_("business_id", business_ids)
        .not_.is_("wellness_signal", "null")
        .execute()
    )
    reviews = reviews_resp.data
    review_count = len(reviews)

    # Top themes
    theme_counter: Counter = Counter()
    for review in reviews:
        for tag in (review.get("theme_tags") or []):
            theme_counter[tag] += 1
    top_themes = dict(theme_counter.most_common(10))

    # Wellness gap score
    if review_count == 0:
        gap_score = 0.0
    else:
        avg_signal = sum(r["wellness_signal"] for r in reviews) / review_count
        density_factor = 1.0 / math.log10(max(business_count, 2))
        gap_score = min(avg_signal * density_factor, 1.0)

    gap_statement = _gap_template(zip_code, gap_score)

    return {
        "zip_code": zip_code,
        "business_count": business_count,
        "review_count": review_count,
        "top_themes": top_themes,
        "wellness_gap_score": round(gap_score, 4),
        "gap_statement": gap_statement,
        "last_computed": datetime.now(timezone.utc).isoformat(),
    }


def run_all_zips(client: Client) -> None:
    """
    Compute and upsert zip_summaries for every distinct zip_code
    currently present in the businesses table.
    """
    # Pull all distinct ZIP codes from businesses
    resp = client.table("businesses").select("zip_code").execute()
    zip_codes: list[str] = list({row["zip_code"] for row in resp.data if row.get("zip_code")})

    if not zip_codes:
        print("No businesses found — nothing to aggregate.")
        return

    print(f"Aggregating {len(zip_codes)} ZIP code(s)...")

    for zip_code in tqdm(zip_codes, desc="ZIP aggregation"):
        summary = compute_zip_summary(client, zip_code)
        client.table("zip_summaries").upsert(summary, on_conflict="zip_code").execute()

    print("ZIP summary upsert complete.")
