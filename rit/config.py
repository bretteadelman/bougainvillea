"""
config.py — Load environment variables and define pipeline constants.
"""

import os
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL: str = os.environ["SUPABASE_URL"]
SUPABASE_ANON_KEY: str = os.environ["SUPABASE_ANON_KEY"]
SUPABASE_SERVICE_KEY: str = os.environ["SUPABASE_SERVICE_KEY"]
GOOGLE_PLACES_API_KEY: str = os.environ["GOOGLE_PLACES_API_KEY"]

_PLACEHOLDER = "REPLACE_WITH_SERVICE_KEY"
if SUPABASE_SERVICE_KEY == _PLACEHOLDER:
    raise EnvironmentError(
        "SUPABASE_SERVICE_KEY is still the placeholder value. "
        "Open rit/.env and replace it with your actual Supabase service role key."
    )

# ---------------------------------------------------------------------------
# Seed data: target ZIP codes (LA metro wellness corridors)
# ---------------------------------------------------------------------------
TARGET_ZIPS: list[str] = [
    "90004", "90005", "90006", "90010", "90019",  # Koreatown / Mid-City
    "90024", "90025", "90034", "90035", "90036",  # West LA / Pico-Robertson
    "90039", "90041", "90065",                     # Atwater / Eagle Rock / Mt. Washington
    "90049", "90272",                              # Brentwood / Pacific Palisades
    "90210", "90211", "90212",                     # Beverly Hills
    "90232", "90291", "90292",                     # Culver City / Venice / MDR
    "90402", "90403", "90405",                     # Santa Monica
]

# ---------------------------------------------------------------------------
# Seed data: practice types to query
# ---------------------------------------------------------------------------
TARGET_PRACTICE_TYPES: list[str] = [
    "med_spa",
    "float_tank",
    "infrared_sauna",
    "nad+",
    "red_light_therapy",
]
