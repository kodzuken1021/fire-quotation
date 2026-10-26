"""Small security helpers."""
import math
import time
from collections import defaultdict, deque


class LoginThrottle:
    """Blocks repeated failed logins for a while.

    Kept in memory, so it resets when the server restarts. That is fine for a school
    project; a production site would store the counters in Redis or the database.
    """

    def __init__(self, max_attempts=5, window_seconds=300):
        self._max = max_attempts
        self._window = window_seconds
        self._fails = defaultdict(deque)      # key -> timestamps of recent failures

    def _recent(self, key):
        now = time.time()
        q = self._fails[key]
        while q and now - q[0] > self._window:
            q.popleft()
        return q

    def is_blocked(self, key):
        return len(self._recent(key)) >= self._max

    def minutes_left(self, key):
        q = self._recent(key)
        if not q:
            return 0
        return max(1, math.ceil((self._window - (time.time() - q[0])) / 60))

    def record_failure(self, key):
        self._recent(key).append(time.time())

    def reset(self, key):
        self._fails.pop(key, None)


login_throttle = LoginThrottle()
