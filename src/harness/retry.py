"""Retry policy: exponential backoff with full jitter, honouring Retry-After."""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime

from src.harness.errors import HarnessError, RateLimitError


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    """``max_retries`` extra attempts after the first one.

    Only errors flagged ``retryable`` (429, 5xx, 408, connect/read timeouts and
    connection failures) are repeated, and only before the first stream event
    reaches the caller; a stream that dies halfway is reported, not replayed.
    """

    max_retries: int = 3
    base_delay: float = 0.5
    max_delay: float = 8.0
    max_retry_after: float = 60.0

    def should_retry(self, error: HarnessError, attempt: int) -> bool:
        """``attempt`` is 1 for the first try."""
        return error.retryable and attempt <= self.max_retries

    def delay(self, error: HarnessError, attempt: int, rng: random.Random | None = None) -> float:
        if isinstance(error, RateLimitError) and error.retry_after is not None:
            return min(max(error.retry_after, 0.0), self.max_retry_after)
        ceiling = min(self.max_delay, self.base_delay * (2 ** (attempt - 1)))
        return (rng or random).uniform(0, ceiling)  # noqa: S311 - jitter, not crypto


def parse_retry_after(value: str | None, now: datetime | None = None) -> float | None:
    """Parse a Retry-After header: delta-seconds or an HTTP-date."""
    if not value:
        return None
    value = value.strip()
    try:
        return max(float(value), 0.0)
    except ValueError:
        pass
    try:
        when = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=UTC)
    current = now or datetime.now(UTC)
    return max((when - current).total_seconds(), 0.0)
