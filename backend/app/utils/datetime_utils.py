"""Datetime utilities."""
from datetime import datetime, timezone

def get_utc_timestamp() -> str:
    """Return current UTC timestamp in ISO format."""
    return datetime.now(timezone.utc).isoformat()
