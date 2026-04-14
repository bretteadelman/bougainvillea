# Bougainvillea — Review Intelligence Tool (RIT)

ETL pipeline that collects Google and Yelp reviews for wellness businesses across
target LA ZIP codes, scores them with NLP, and stores results in Supabase.

---

## Setup

```bash
# 1. Move into the rit directory
cd rit

# 2. Create and activate a virtual environment
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Install Playwright browsers (needed for full review scraping)
playwright install chromium

# 5. Add your Supabase service role key to .env
#    Open rit/.env and replace REPLACE_WITH_SERVICE_KEY with the real value.
#    Find it at: Supabase Dashboard → Project Settings → API → service_role key
```

---

## Running the pipeline

```bash
# Scrape Google + Yelp for all target ZIP codes and practice types
python run.py --scrape

# NLP-score all unscored reviews (wellness signal, sentiment, theme tags)
python run.py --score

# Recompute ZIP-level wellness gap summaries
python run.py --aggregate

# Run the full pipeline end-to-end
python run.py --all
```

---

## File overview

| File | Purpose |
|------|---------|
| `config.py` | Env vars, target ZIPs, practice types |
| `db.py` | Supabase client singleton (service key) |
| `scraper.py` | Google + Yelp scraping stubs; upsert helpers |
| `scorer.py` | NLP wellness signal, sentiment, theme tagging |
| `aggregator.py` | ZIP-level summary computation and upsert |
| `run.py` | CLI entry point |

---

## Implementing the scrapers

Both `scrape_google()` and `scrape_yelp()` in `scraper.py` are stubs.
Implement them one at a time:

1. **Google** — Use the [Places API Text Search](https://developers.google.com/maps/documentation/places/web-service/text-search).
   Add `GOOGLE_PLACES_API_KEY` to `.env`. For full review lists (>5), scrape
   the Maps URL with Playwright.

2. **Yelp** — Use the [Yelp Fusion Business Search API](https://docs.developer.yelp.com/reference/v3_business_search).
   Add `YELP_API_KEY` to `.env`. Free tier returns 3 reviews per business;
   use Playwright for full scraping.

Each function must return a list of business dicts — see the shape documented
at the top of `scraper.py`.

---

## Notes

- The `.env` file is gitignored. Never commit API keys.
- All database writes use the service role key. The anon key is loaded but
  reserved for future read-only / client-side use.
- NLP fields (`wellness_signal`, `theme_tags`, `sentiment`) are `NULL` on
  insert and backfilled by `--score`. This keeps scraping and scoring decoupled.
