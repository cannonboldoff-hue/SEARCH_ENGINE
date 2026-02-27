"""Shared API constants."""

from datetime import datetime, timezone

# Vector size used by DB and embedding normalization (match migration 018)
EMBEDDING_DIM = 324

# Searches never expire until the user deletes them (use far-future date)
SEARCH_NEVER_EXPIRES = datetime(9999, 12, 31, 23, 59, 59, tzinfo=timezone.utc)
