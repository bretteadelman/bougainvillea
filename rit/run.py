"""
run.py — Main entry point for the RIT ETL pipeline.

Usage:
    python run.py --scrape       # Scrape Google + Yelp for all target ZIPs
    python run.py --score        # NLP-score unscored reviews
    python run.py --aggregate    # Recompute zip_summaries
    python run.py --all          # Full pipeline in sequence: scrape → score → aggregate
"""

import argparse
import sys

from db import get_client
from config import TARGET_ZIPS, TARGET_PRACTICE_TYPES


def run_scrape() -> None:
    from scraper import scrape_google, scrape_yelp, upsert_business, insert_reviews
    from tqdm import tqdm

    client = get_client()

    combos = [(z, p) for z in TARGET_ZIPS for p in TARGET_PRACTICE_TYPES]
    print(f"Scraping {len(combos)} ZIP × practice-type combinations...")

    for zip_code, practice_type in tqdm(combos, desc="Scraping"):
        for source, scrape_fn in [("google", scrape_google), ("yelp", scrape_yelp)]:
            businesses = scrape_fn(zip_code, practice_type)
            for biz in businesses:
                business_id = upsert_business(client, biz)
                insert_reviews(client, business_id, biz.get("reviews", []))

    print("Scraping complete.")


def run_score() -> None:
    from scorer import score_reviews_batch

    client = get_client()
    print("Scoring unscored reviews...")
    score_reviews_batch(client)


def run_aggregate() -> None:
    from aggregator import run_all_zips

    client = get_client()
    print("Aggregating ZIP summaries...")
    run_all_zips(client)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Bougainvillea Review Intelligence Tool (RIT) — ETL pipeline"
    )
    parser.add_argument("--scrape", action="store_true", help="Run scraper for all target ZIPs")
    parser.add_argument("--score", action="store_true", help="Run NLP scorer on unscored reviews")
    parser.add_argument("--aggregate", action="store_true", help="Recompute zip_summaries")
    parser.add_argument("--all", dest="run_all", action="store_true", help="Run full pipeline")

    args = parser.parse_args()

    if not any([args.scrape, args.score, args.aggregate, args.run_all]):
        parser.print_help()
        sys.exit(1)

    if args.run_all or args.scrape:
        run_scrape()

    if args.run_all or args.score:
        run_score()

    if args.run_all or args.aggregate:
        run_aggregate()


if __name__ == "__main__":
    main()
