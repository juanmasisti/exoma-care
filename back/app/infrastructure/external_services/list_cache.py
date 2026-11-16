from collections import OrderedDict
from copy import deepcopy
from threading import Lock
from time import monotonic
from typing import Any


class TTLListCache:
    def __init__(
        self,
        ttl_seconds: float = 600,
        max_entries: int = 256,
    ):
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds debe ser mayor a cero.")
        if max_entries <= 0:
            raise ValueError("max_entries debe ser mayor a cero.")
        self._ttl_seconds = ttl_seconds
        self._max_entries = max_entries
        self._entries: OrderedDict[str, tuple[float, Any]] = OrderedDict()
        self._lock = Lock()

    def get(self, key: str) -> Any | None:
        now = monotonic()
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return None
            expires_at, value = entry
            if expires_at <= now:
                del self._entries[key]
                return None
            self._entries.move_to_end(key)
            return deepcopy(value)

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            self._entries[key] = (monotonic() + self._ttl_seconds, deepcopy(value))
            self._entries.move_to_end(key)
            while len(self._entries) > self._max_entries:
                self._entries.popitem(last=False)


apigen_list_cache = TTLListCache(ttl_seconds=600, max_entries=256)
