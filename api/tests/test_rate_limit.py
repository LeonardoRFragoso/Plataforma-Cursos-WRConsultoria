from datetime import UTC, datetime, timedelta

from app.core.rate_limit import RateLimiter


def test_rate_limiter_allows_within_limit():
    limiter = RateLimiter(max_requests=3, window_seconds=60)
    assert limiter.is_allowed("ip-1", datetime.now(UTC)) is True
    assert limiter.is_allowed("ip-1", datetime.now(UTC)) is True
    assert limiter.is_allowed("ip-1", datetime.now(UTC)) is True


def test_rate_limiter_blocks_over_limit():
    now = datetime.now(UTC)
    limiter = RateLimiter(max_requests=2, window_seconds=60)
    assert limiter.is_allowed("ip-1", now) is True
    assert limiter.is_allowed("ip-1", now + timedelta(seconds=1)) is True
    assert limiter.is_allowed("ip-1", now + timedelta(seconds=2)) is False


def test_rate_limiter_resets_after_window():
    now = datetime.now(UTC)
    limiter = RateLimiter(max_requests=1, window_seconds=1)
    assert limiter.is_allowed("ip-1", now) is True
    assert limiter.is_allowed("ip-1", now + timedelta(seconds=0.5)) is False
    assert limiter.is_allowed("ip-1", now + timedelta(seconds=2)) is True
