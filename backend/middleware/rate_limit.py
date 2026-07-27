"""
Per-user rate limiter for chat endpoints. Uses in-memory sliding window.
No external dependencies — reuses the same TTL-dict pattern as the chat cache.
"""
from collections import defaultdict
import time

_user_requests: dict = defaultdict(list)  # user_id -> [timestamps]
_RATE_LIMIT = 5   # max chat requests per user per minute
_WINDOW = 60      # sliding window in seconds


def check_rate_limit(user_id: str) -> bool:
    """Return True if under limit, False if rate-limited."""
    now = time.time()
    window = [t for t in _user_requests[user_id] if now - t < _WINDOW]
    _user_requests[user_id] = window
    if len(window) >= _RATE_LIMIT:
        return False
    _user_requests[user_id].append(now)
    return True


def rate_limit_remaining(user_id: str) -> int:
    """How many requests left in current window."""
    now = time.time()
    window = [t for t in _user_requests[user_id] if now - t < _WINDOW]
    return max(0, _RATE_LIMIT - len(window))
