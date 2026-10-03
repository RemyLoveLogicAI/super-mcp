"""Typed provider errors.

Every failure that leaves the harness is one of these, so callers (the CLI
and the TUI) can tell an authentication problem from a rate limit, a dead
endpoint, or a server that answered with garbage. Messages never contain
API keys: request headers are never interpolated into them.
"""

from __future__ import annotations


class HarnessError(Exception):
    """Base class for every provider-harness failure."""

    #: Process exit code the CLI uses for this error class.
    exit_code: int = 1
    #: Whether the retry policy may repeat the request.
    retryable: bool = False

    def __init__(self, message: str, *, provider: str | None = None) -> None:
        super().__init__(message)
        self.provider = provider

    def __str__(self) -> str:
        base = super().__str__()
        return f"[{self.provider}] {base}" if self.provider else base


class ConfigError(HarnessError):
    """Invalid or incomplete provider configuration (bad URL, missing model...)."""

    exit_code = 2


class AuthenticationError(HarnessError):
    """The endpoint rejected the credentials (HTTP 401/403) or none were supplied."""

    exit_code = 3


class ProviderHTTPError(HarnessError):
    """A non-success HTTP status that has no more specific class."""

    exit_code = 6

    def __init__(
        self,
        message: str,
        *,
        status_code: int,
        provider: str | None = None,
        body_excerpt: str = "",
    ) -> None:
        super().__init__(message, provider=provider)
        self.status_code = status_code
        self.body_excerpt = body_excerpt
        self.retryable = status_code >= 500


class RateLimitError(ProviderHTTPError):
    """HTTP 429. ``retry_after`` carries the server's hint in seconds, if any."""

    exit_code = 5

    def __init__(
        self,
        message: str,
        *,
        provider: str | None = None,
        retry_after: float | None = None,
        body_excerpt: str = "",
    ) -> None:
        super().__init__(message, status_code=429, provider=provider, body_excerpt=body_excerpt)
        self.retry_after = retry_after
        self.retryable = True


class ProviderTimeoutError(HarnessError):
    """Connect, read, or overall request timeout."""

    exit_code = 4
    retryable = True


class ProviderConnectionError(HarnessError):
    """The endpoint could not be reached (DNS, refused, reset, TLS)."""

    exit_code = 4
    retryable = True


class BadResponseError(HarnessError):
    """The endpoint answered, but not with the protocol we expected."""

    exit_code = 6
