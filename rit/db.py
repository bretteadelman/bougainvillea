"""
db.py — Supabase client singleton.

All writes must use the service key client returned here.
Never use the anon key for mutations.
"""

from functools import lru_cache
from supabase import create_client, Client
from config import SUPABASE_URL, SUPABASE_SERVICE_KEY


@lru_cache(maxsize=1)
def get_client() -> Client:
    """Return a cached Supabase client authenticated with the service role key."""
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
