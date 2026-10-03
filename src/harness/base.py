"""Provider base: shared HTTP transport, status mapping, retries, and the ABC.

Concrete providers implement payload building, stream parsing and health
checks; everything about getting a healthy streaming response (timeouts,
retry/backoff, typed errors) lives here once.
"""

from __future__ import annotations

import asyncio
import json
import time
from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator, AsyncIterator, Awaitable, Callable, Mapping
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any, Self

import httpx
import structlog

from src.harness.config import ProviderProfile, Secret, resolve_api_key
from src.harness.errors import (
    AuthenticationError,
    BadResponseError,
    ConfigError,
    HarnessError,
    ProviderConnectionError,
    ProviderHTTPError,
    ProviderTimeoutError,
    RateLimitError,
)
from src.harness.retry import RetryPolicy, parse_retry_after
from src.harness.sse import SSEEvent, iter_sse

if TYPE_CHECKING:
    from types import TracebackType

    from src.harness.types import ChatRequest, HealthReport, StreamEvent

logger = structlog.get_logger(__name__)

Sleep = Callable[[float], Awaitable[None]]
_BODY_EXCERPT = 2048


class BaseProvider(ABC):
    """One configured endpoint. Use as an async context manager or call :meth:`aclose`."""

    def __init__(
        self,
        profile: ProviderProfile,
        *,
        api_key: Secret | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
        retry: RetryPolicy | None = None,
        sleep: Sleep = asyncio.sleep,
    ) -> None:
        self.profile = profile
        self._api_key = api_key if api_key is not None else resolve_api_key(profile)
        self._retry = retry or RetryPolicy(max_retries=profile.max_retries)
        self._sleep = sleep
        #: Called as ``on_retry(error, attempt, delay_s)`` before each backoff sleep.
        self.on_retry: Callable[[HarnessError, int, float], None] | None = None
        self._client = httpx.AsyncClient(
            base_url=profile.base_url.rstrip("/") + "/",
            timeout=httpx.Timeout(
                connect=profile.connect_timeout,
                read=profile.read_timeout,
                write=profile.connect_timeout,
                pool=profile.connect_timeout,
            ),
            transport=transport,
            headers={"User-Agent": "super-mcp-harness/1.0", **dict(profile.headers)},
        )

    # ── Public API ──────────────────────────────────────────────

    @property
    def name(self) -> str:
        return self.profile.name

    @property
    def model(self) -> str:
        return self.profile.model

    @property
    def endpoint(self) -> str:
        return self.profile.base_url

    @abstractmethod
    def stream_chat(self, request: ChatRequest) -> AsyncGenerator[StreamEvent, None]:
        """Stream one completion as provider-neutral events.

        Cancel by cancelling the consuming task (or closing the iterator):
        the HTTP response is closed immediately, which stops generation on
        servers that watch the connection.
        """

    @abstractmethod
    async def check_health(self) -> HealthReport:
        """Probe the endpoint. Never raises :class:`HarnessError`; failures are in the report."""

    async def aclose(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.aclose()

    # ── Subclass hooks ──────────────────────────────────────────

    @abstractmethod
    def _auth_headers(self) -> dict[str, str]:
        """Credential headers; must be empty when there is no key."""

    # ── Transport helpers ───────────────────────────────────────

    def _require_model(self) -> str:
        if not self.profile.model:
            raise ConfigError(
                "no model selected; pass --model or set model in the profile", provider=self.name
            )
        return self.profile.model

    @asynccontextmanager
    async def _open_stream(
        self, path: str, payload: Mapping[str, Any]
    ) -> AsyncIterator[httpx.Response]:
        """POST ``payload`` and yield a 2xx streaming response, retrying transient failures.

        Retries happen only while establishing the response, so a caller never
        sees duplicated tokens.
        """
        attempt = 0
        while True:
            attempt += 1
            request = self._client.build_request(
                "POST",
                path,
                json=payload,
                headers={**self._auth_headers(), "Accept": "text/event-stream"},
            )
            try:
                response = await self._send(request)
            except HarnessError as err:
                if not self._retry.should_retry(err, attempt):
                    raise
                delay = self._retry.delay(err, attempt)
                await logger.awarning(
                    "provider_retry",
                    provider=self.name,
                    attempt=attempt,
                    delay_s=round(delay, 2),
                    error=type(err).__name__,
                )
                if self.on_retry is not None:
                    self.on_retry(err, attempt, delay)
                await self._sleep(delay)
                continue
            try:
                yield response
            finally:
                await response.aclose()
            return

    async def _send(self, request: httpx.Request) -> httpx.Response:
        try:
            response = await self._client.send(request, stream=True)
        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError(
                f"timed out contacting {self.endpoint} ({type(exc).__name__})", provider=self.name
            ) from exc
        except httpx.TransportError as exc:
            raise ProviderConnectionError(
                f"cannot reach {self.endpoint}: {exc or type(exc).__name__}", provider=self.name
            ) from exc
        if response.is_success:
            return response
        try:
            body = await self._read_excerpt(response)
        finally:
            await response.aclose()
        raise self._status_error(response, body)

    @staticmethod
    async def _read_excerpt(response: httpx.Response) -> str:
        chunks: list[bytes] = []
        size = 0
        try:
            async for chunk in response.aiter_bytes():
                chunks.append(chunk)
                size += len(chunk)
                if size >= _BODY_EXCERPT:
                    break
        except httpx.HTTPError:
            pass
        return b"".join(chunks)[:_BODY_EXCERPT].decode("utf-8", errors="replace")

    def _status_error(self, response: httpx.Response, body: str) -> HarnessError:
        status = response.status_code
        body = self._redact(body)
        detail = extract_error_message(body) or response.reason_phrase or "error"
        message = f"HTTP {status} from {self.endpoint}: {detail}"
        if status in (401, 403):
            hint = ""
            if self._api_key is None and self.profile.api_key_env:
                hint = f" (no key sent; set {self.profile.api_key_env})"
            return AuthenticationError(message + hint, provider=self.name)
        if status == 429:
            return RateLimitError(
                message,
                provider=self.name,
                retry_after=parse_retry_after(response.headers.get("retry-after")),
                body_excerpt=body,
            )
        if status == 408:
            return ProviderTimeoutError(message, provider=self.name)
        if status == 404 and self.profile.model:
            message += f" (check the endpoint path and that model {self.profile.model!r} exists)"
        return ProviderHTTPError(message, status_code=status, provider=self.name, body_excerpt=body)

    def _redact(self, text: str) -> str:
        """Remove the API key if a server echoes it back in an error body."""
        if self._api_key is not None and self._api_key.reveal():
            return text.replace(self._api_key.reveal(), "[REDACTED]")
        return text

    async def _sse(self, response: httpx.Response) -> AsyncIterator[SSEEvent]:
        """SSE events from a response, mapping mid-stream transport failures."""
        try:
            async for event in iter_sse(response.aiter_text()):
                yield event
        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError(
                f"no data from {self.endpoint} for {self.profile.read_timeout:.0f}s mid-stream",
                provider=self.name,
            ) from exc
        except httpx.TransportError as exc:
            raise ProviderConnectionError(
                f"stream from {self.endpoint} interrupted: {exc or type(exc).__name__}",
                provider=self.name,
            ) from exc

    async def _get_json(self, path: str) -> tuple[Any, float]:
        """Single-attempt GET for health checks. Returns (json, latency_ms)."""
        started = time.perf_counter()
        request = self._client.build_request("GET", path, headers=self._auth_headers())
        response = await self._send(request)
        try:
            raw = await response.aread()
        finally:
            await response.aclose()
        latency = (time.perf_counter() - started) * 1000
        try:
            return json.loads(raw), latency
        except ValueError as exc:
            raise BadResponseError(
                f"{self.endpoint}/{path} returned non-JSON", provider=self.name
            ) from exc


def extract_error_message(body: str) -> str:
    """Pull a human message out of the common JSON error shapes."""
    body = body.strip()
    if not body:
        return ""
    try:
        data = json.loads(body)
    except ValueError:
        return body[:300]
    if isinstance(data, dict):
        err = data.get("error", data)
        if isinstance(err, dict):
            msg = err.get("message") or err.get("detail") or err.get("type")
            if isinstance(msg, str):
                return msg[:300]
        if isinstance(err, str):
            return err[:300]
        for key in ("message", "detail"):
            if isinstance(data.get(key), str):
                return str(data[key])[:300]
    return body[:300]
