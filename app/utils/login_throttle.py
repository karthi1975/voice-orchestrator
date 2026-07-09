"""In-memory failed-login throttle (brute-force protection).

Tracks failed attempts per key (e.g. identifier and client IP). After
`max_failures` consecutive failures the key is locked for `lockout_seconds`;
a successful login clears it. State is per-process and lost on restart —
adequate for the current single-instance deployment; swap for a shared
store if the app ever runs multiple replicas.
"""

import threading
import time
from typing import Dict, Tuple


class LoginThrottle:
    def __init__(self, max_failures: int = 5, lockout_seconds: int = 900,
                 window_seconds: int = 900):
        self._max = max_failures
        self._lockout = lockout_seconds
        self._window = window_seconds
        self._lock = threading.Lock()
        # key -> (failure_count, window_start_ts, locked_until_ts)
        self._state: Dict[str, Tuple[int, float, float]] = {}

    def is_locked(self, *keys: str) -> bool:
        """True if ANY of the given keys is currently locked out."""
        now = time.time()
        with self._lock:
            for key in keys:
                if not key:
                    continue
                count, start, locked_until = self._state.get(key, (0, now, 0.0))
                if locked_until > now:
                    return True
            return False

    def record_failure(self, *keys: str) -> None:
        now = time.time()
        with self._lock:
            # Opportunistic cleanup so the map can't grow unbounded.
            if len(self._state) > 10_000:
                self._state = {
                    k: v for k, v in self._state.items()
                    if v[2] > now or now - v[1] < self._window
                }
            for key in keys:
                if not key:
                    continue
                count, start, locked_until = self._state.get(key, (0, now, 0.0))
                if now - start > self._window:
                    count, start = 0, now
                count += 1
                if count >= self._max:
                    locked_until = now + self._lockout
                self._state[key] = (count, start, locked_until)

    def record_success(self, *keys: str) -> None:
        with self._lock:
            for key in keys:
                self._state.pop(key, None)
