"""Rate limiting in-memory simples para a API."""

from collections import defaultdict
from datetime import UTC, datetime, timedelta

from app.core.config import settings


class RateLimiter:
    """Limitador por IP com janela deslizante."""

    def __init__(self, max_requests: int, window_seconds: int):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: dict[str, list[datetime]] = defaultdict(list)

    def is_allowed(self, key: str, now: datetime | None = None) -> bool:
        if now is None:
            now = datetime.now(UTC)
        cutoff = now - timedelta(seconds=self.window_seconds)
        timestamps = [t for t in self._requests[key] if t > cutoff]
        self._requests[key] = timestamps

        if len(timestamps) >= self.max_requests:
            return False

        timestamps.append(now)
        return True


limiter = RateLimiter(
    max_requests=settings.RATE_LIMIT_REQUESTS,
    window_seconds=settings.RATE_LIMIT_WINDOW_SECONDS,
)
