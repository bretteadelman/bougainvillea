"""
scraper.py — Scraping stubs for Google and Yelp business/review data.

Each scrape function returns a list of dicts conforming to the shapes
documented below. Actual scraping logic is left as TODOs; implement one
platform at a time and validate against the upsert helpers before moving on.
"""

from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from typing import Any

import requests
from supabase import Client

from config import GOOGLE_PLACES_API_KEY

# ---------------------------------------------------------------------------
# Google Places API constants
# ---------------------------------------------------------------------------
_PLACES_TEXT_SEARCH_URL = "https://maps.googleapis.com/maps/api/place/textsearch/json"
_PLACES_DETAILS_URL = "https://maps.googleapis.com/maps/api/place/details/json"

# Map internal practice type slugs to human-readable search terms
_PRACTICE_TYPE_LABELS: dict[str, str] = {
    "med_spa":           "med spa",
    "float_tank":        "float tank sensory deprivation",
    "infrared_sauna":    "infrared sauna",
    "nad+":              "NAD+ IV therapy",
    "red_light_therapy": "red light therapy",
}


# ---------------------------------------------------------------------------
# Expected shape: business dict
# ---------------------------------------------------------------------------
# {
#     "name": str,
#     "address": str,
#     "zip_code": str,
#     "city": str,
#     "neighborhood": str | None,
#     "google_place_id": str | None,
#     "yelp_id": str | None,
#     "google_rating": float | None,
#     "yelp_rating": float | None,
#     "google_review_count": int | None,
#     "yelp_review_count": int | None,
#     "practice_type": str,
#     "reviews": list[review_dict],   # may be empty; inserted separately
# }

# Expected shape: review dict
# {
#     "platform": "google" | "yelp",
#     "rating": float,
#     "text": str,
#     "review_date": str,   # ISO date string, e.g. "2024-03-15"
# }
# NLP fields (wellness_signal, theme_tags, sentiment) are left NULL on insert
# and backfilled later by scorer.py.


def scrape_google(zip_code: str, practice_type: str) -> list[dict[str, Any]]:
    """
    Search Google Places Text Search for businesses matching practice_type in
    zip_code. Paginates up to 3 pages (60 results). For each place, fetches
    Place Details to get address components, rating, review count, and up to
    5 reviews.

    Returns a list of business dicts matching the shape at the top of this file.
    """
    label = _PRACTICE_TYPE_LABELS.get(practice_type, practice_type.replace("_", " "))
    query = f"{label} {zip_code} Los Angeles CA"

    businesses: list[dict[str, Any]] = []
    params: dict[str, Any] = {
        "query": query,
        "key": GOOGLE_PLACES_API_KEY,
    }

    # Paginate through up to 3 pages of results (20 per page)
    for _ in range(3):
        resp = requests.get(_PLACES_TEXT_SEARCH_URL, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        status = data.get("status")
        if status == "ZERO_RESULTS":
            break
        if status not in ("OK",):
            # INVALID_REQUEST on page 2+ usually means the page token expired — stop paginating
            break

        for place in data.get("results", []):
            detail = _fetch_place_details(place["place_id"])
            if detail:
                businesses.append(_parse_place(detail, zip_code, practice_type))

        next_token = data.get("next_page_token")
        if not next_token:
            break

        # Google requires a short delay before next_page_token becomes valid
        time.sleep(3)
        params = {"pagetoken": next_token, "key": GOOGLE_PLACES_API_KEY}

    return businesses


def _fetch_place_details(place_id: str) -> dict[str, Any] | None:
    """Fetch full Place Details for a single place_id."""
    params = {
        "place_id": place_id,
        "fields": (
            "place_id,name,formatted_address,address_components,"
            "rating,user_ratings_total,reviews"
        ),
        "key": GOOGLE_PLACES_API_KEY,
    }
    resp = requests.get(_PLACES_DETAILS_URL, params=params, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    if data.get("status") == "OK":
        return data.get("result")
    return None


def _parse_place(detail: dict[str, Any], zip_code: str, practice_type: str) -> dict[str, Any]:
    """Convert a Place Details result into the standard business dict shape."""
    # Extract zip and city from address_components
    parsed_zip = zip_code
    city = "Los Angeles"
    for component in detail.get("address_components", []):
        types = component.get("types", [])
        if "postal_code" in types:
            parsed_zip = component["short_name"]
        if "locality" in types:
            city = component["long_name"]

    # Convert raw reviews to the standard review dict shape
    reviews: list[dict[str, Any]] = []
    for r in detail.get("reviews", []):
        # Google returns relative_time_description; convert Unix timestamp if available
        review_date = None
        if r.get("time"):
            review_date = datetime.fromtimestamp(r["time"], tz=timezone.utc).date().isoformat()
        reviews.append({
            "platform": "google",
            "rating": float(r.get("rating", 0)),
            "text": r.get("text", ""),
            "review_date": review_date,
        })

    return {
        "name": detail.get("name", ""),
        "address": detail.get("formatted_address", ""),
        "zip_code": parsed_zip,
        "city": city,
        "neighborhood": None,  # not returned by Places API
        "google_place_id": detail.get("place_id"),
        "yelp_id": None,
        "google_rating": detail.get("rating"),
        "yelp_rating": None,
        "google_review_count": detail.get("user_ratings_total"),
        "yelp_review_count": None,
        "practice_type": practice_type,
        "reviews": reviews,
    }


def scrape_yelp(zip_code: str, practice_type: str) -> list[dict[str, Any]]:
    """
    Search Yelp for businesses matching practice_type in zip_code.

    TODO:
      - Use the Yelp Fusion API (Business Search endpoint) with an API key
        stored in .env as YELP_API_KEY.
      - Paginate with offset until total is exhausted (max 1000 results).
      - For each business, fetch reviews via the Reviews endpoint (3 per
        business via free tier) or scrape the full review list with Playwright.
      - Return a list of business dicts matching the shape above.

    Returns an empty list until implemented.
    """
    # TODO: implement
    return []


def upsert_business(client: Client, business: dict[str, Any]) -> str:
    """
    Upsert a business record into the businesses table.

    Conflict resolution:
      - If google_place_id is present, upsert on that column.
      - Else if yelp_id is present, upsert on that column.
      - Else insert as new (edge case — should not happen in normal flow).

    Returns the UUID of the upserted business row.
    """
    now = datetime.now(timezone.utc).isoformat()

    row = {
        "name": business["name"],
        "address": business["address"],
        "zip_code": business["zip_code"],
        "city": business.get("city", "Los Angeles"),
        "neighborhood": business.get("neighborhood"),
        "google_place_id": business.get("google_place_id"),
        "yelp_id": business.get("yelp_id"),
        "google_rating": business.get("google_rating"),
        "yelp_rating": business.get("yelp_rating"),
        "google_review_count": business.get("google_review_count"),
        "yelp_review_count": business.get("yelp_review_count"),
        "practice_type": business["practice_type"],
        "collected_at": now,
    }

    # Determine conflict column for upsert
    if business.get("google_place_id"):
        conflict_col = "google_place_id"
    elif business.get("yelp_id"):
        conflict_col = "yelp_id"
    else:
        # No unique identifier available — assign a new UUID and plain-insert
        row["id"] = str(uuid.uuid4())
        result = client.table("businesses").insert(row).execute()
        return result.data[0]["id"]

    result = (
        client.table("businesses")
        .upsert(row, on_conflict=conflict_col)
        .execute()
    )
    return result.data[0]["id"]


def insert_reviews(
    client: Client,
    business_id: str,
    reviews: list[dict[str, Any]],
) -> None:
    """
    Insert new reviews for a given business, skipping any that already exist.

    Deduplication is based on (business_id, platform, review_date, text).
    NLP fields (wellness_signal, theme_tags, sentiment) are intentionally
    omitted here — scorer.py backfills them in a separate pass.

    Skips insert if reviews list is empty.
    """
    if not reviews:
        return

    # Fetch existing reviews for this business to build a dedup set
    existing_resp = (
        client.table("reviews")
        .select("platform, review_date, text")
        .eq("business_id", business_id)
        .execute()
    )
    existing: set[tuple] = {
        (r["platform"], r.get("review_date"), (r.get("text") or "")[:100])
        for r in existing_resp.data
    }

    now = datetime.now(timezone.utc).isoformat()

    new_rows = []
    for review in reviews:
        key = (
            review["platform"],
            review.get("review_date"),
            (review.get("text") or "")[:100],
        )
        if key in existing:
            continue
        new_rows.append({
            "id": str(uuid.uuid4()),
            "business_id": business_id,
            "platform": review["platform"],
            "rating": review["rating"],
            "text": review.get("text", ""),
            "review_date": review.get("review_date"),
            # NLP fields left NULL — backfilled by scorer.py
            "theme_tags": None,
            "wellness_signal": None,
            "sentiment": None,
            "collected_at": now,
        })

    if new_rows:
        client.table("reviews").insert(new_rows).execute()
