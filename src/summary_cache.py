"""
Timestamped in-process cache for generated client summaries.

CLAUDE.md's third performance lever: repeat lookups of the same client
(the common RM workflow — flipping between a handful of clients) should
not pay the ~5-10s fetch+narration cost again while the data is fresh.

Design notes:
- Keyed by APR_CLIENT_CODE; values are the full generate_all_summaries()
  result dicts (summaries + tab_data + rules + generated_at).
- TTL-based: entries older than SUMMARY_CACHE_TTL_SECONDS (env, default
  600s) are treated as absent — dashboards are a snapshot view, not a
  live feed, so minutes-level staleness is acceptable and bounded.
- LRU size cap so a long-running process can't grow unbounded.
- Thread-safe (Streamlit runs one script thread per session against a
  shared process).
- In-process by design. A Redis tier would only pay off with multiple app
  processes; the interface (get/put/invalidate) is the shape a Redis
  implementation would keep.
"""
import os
import threading
import time
from collections import OrderedDict
from typing import Any, Dict, Optional

DEFAULT_TTL_SECONDS = int(os.getenv("SUMMARY_CACHE_TTL_SECONDS", "600"))
MAX_ENTRIES = 64

_lock = threading.Lock()
_store: "OrderedDict[str, tuple]" = OrderedDict()  # code -> (stored_at, value)


def get(client_code: str,
        ttl_seconds: int = None) -> Optional[Dict[str, Any]]:
    """Cached result for the client, or None if absent/expired."""
    ttl = DEFAULT_TTL_SECONDS if ttl_seconds is None else ttl_seconds
    with _lock:
        entry = _store.get(client_code)
        if entry is None:
            return None
        stored_at, value = entry
        if time.time() - stored_at > ttl:
            del _store[client_code]
            return None
        _store.move_to_end(client_code)
        return value


def put(client_code: str, value: Dict[str, Any]) -> None:
    """Store a result, evicting the least-recently-used entry when full."""
    with _lock:
        _store[client_code] = (time.time(), value)
        _store.move_to_end(client_code)
        while len(_store) > MAX_ENTRIES:
            _store.popitem(last=False)


def invalidate(client_code: str = None) -> None:
    """Drop one client's entry (e.g. the UI's Refresh button), or all."""
    with _lock:
        if client_code is None:
            _store.clear()
        else:
            _store.pop(client_code, None)


def entry_age_seconds(client_code: str) -> Optional[float]:
    """Age of the cached entry in seconds, or None if not cached."""
    with _lock:
        entry = _store.get(client_code)
        return None if entry is None else time.time() - entry[0]
