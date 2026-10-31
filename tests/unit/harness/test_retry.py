from __future__ import annotations

import random
from datetime import UTC, datetime

from src.harness.errors import (
    AuthenticationError,
    ProviderConnectionError,
    ProviderHTTPError,
    RateLimitError,
)
from src.harness.retry import RetryPolicy, parse_retry_after


def test_parse_retry_after_seconds_and_date() -> None:
    assert parse_retry_after("3") == 3.0
    assert parse_retry_after(" 1.5 ") == 1.5
    assert parse_retry_after(None) is None
    assert parse_retry_after("garbage") is None
    now = datetime(2026, 10, 3, 12, 0, 0, tzinfo=UTC)
    assert parse_retry_after("Sat, 03 Oct 2026 12:00:10 GMT", now=now) == 10.0
    assert parse_retry_after("Sat, 03 Oct 2026 11:00:00 GMT", now=now) == 0.0


def test_should_retry_only_retryable_within_budget() -> None:
    p = RetryPolicy(max_retries=2)
    conn = ProviderConnectionError("x")
    assert p.should_retry(conn, 1)
    assert p.should_retry(conn, 2)
    assert not p.should_retry(conn, 3)
    assert not p.should_retry(AuthenticationError("x"), 1)
    assert not p.should_retry(ProviderHTTPError("x", status_code=400), 1)
    assert p.should_retry(ProviderHTTPError("x", status_code=503), 1)
    assert p.should_retry(RateLimitError("x"), 1)


def test_delay_backoff_bounds_and_retry_after() -> None:
    p = RetryPolicy(base_delay=0.5, max_delay=4.0, max_retry_after=30)
    rng = random.Random(1)  # noqa: S311 - deterministic jitter for the test
    for attempt, ceiling in [(1, 0.5), (2, 1.0), (3, 2.0), (4, 4.0), (8, 4.0)]:
        for _ in range(20):
            assert 0 <= p.delay(ProviderConnectionError("x"), attempt, rng) <= ceiling
    assert p.delay(RateLimitError("x", retry_after=7), 1) == 7
    assert p.delay(RateLimitError("x", retry_after=999), 1) == 30
