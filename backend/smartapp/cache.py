"""
A small, bounded, thread-safe TTL cache for SmartApp metadata providers.

Keyed by (provider, package_name) - e.g. ("exodus", "com.example.app") -
so the same package is never fetched from the same provider twice within
the TTL. Bounded (least-recently-used entries are evicted past
`max_entries`), so it can never grow without limit. Negative results
("package not found at this provider") are cached too - a real, verified
answer worth not re-asking - but provider FAILURES are never cached, so a
transient outage doesn't pin "unavailable" for the whole TTL.
"""

import threading
import time
from collections import OrderedDict
from typing import Any, Callable, Hashable

_MISSING = object()


class TTLCache:
    def __init__(self, ttl_seconds: float, max_entries: int = 2048, clock: Callable[[], float] = time.monotonic):
        if max_entries <= 0:
            raise ValueError("max_entries must be positive")
        self._ttl = ttl_seconds
        self._max = max_entries
        self._clock = clock
        self._data: "OrderedDict[Hashable, tuple[float, Any]]" = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key: Hashable, default: Any = _MISSING) -> Any:
        with self._lock:
            entry = self._data.get(key)
            if entry is None:
                return default
            expires_at, value = entry
            if self._clock() >= expires_at:
                del self._data[key]
                return default
            self._data.move_to_end(key)
            return value

    def set(self, key: Hashable, value: Any) -> None:
        with self._lock:
            self._data[key] = (self._clock() + self._ttl, value)
            self._data.move_to_end(key)
            while len(self._data) > self._max:
                self._data.popitem(last=False)

    def get_or_load(self, key: Hashable, loader: Callable[[], Any]) -> Any:
        """Returns the cached value, or calls `loader()` and caches its
        result. Exceptions from `loader` propagate and are NOT cached."""
        cached = self.get(key)
        if cached is not _MISSING:
            return cached
        value = loader()
        self.set(key, value)
        return value

    def clear(self) -> None:
        with self._lock:
            self._data.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._data)


MISSING = _MISSING
