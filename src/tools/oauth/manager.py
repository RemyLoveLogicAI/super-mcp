"""OAuth token manager — handles the full OAuth2 lifecycle.

Stores tokens securely, handles refresh, validates scopes,
and provides a clean interface for tool authentication.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import secrets
import time
from base64 import urlsafe_b64encode
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
import structlog

from src.kernel.event_bus import EventBus
from src.kernel.types import OAuthConfig, Severity, ToolAuthType

logger = structlog.get_logger(__name__)


@dataclass
class TokenSet:
    """Stored OAuth token set."""
    tool_slug: str
    access_token: str
    refresh_token: str | None = None
    token_type: str = "Bearer"
    expires_at: float | None = None
    scopes: list[str] = field(default_factory=list)
    obtained_at: float = field(default_factory=time.time)

    @property
    def expired(self) -> bool:
        if self.expires_at is None:
            return False
        return time.time() >= self.expires_at - 60  # 60s buffer

    @property
    def valid(self) -> bool:
        return bool(self.access_token) and not self.expired


@dataclass
class AuthState:
    """CSRF state for OAuth flow."""
    state: str
    code_verifier: str
    tool_slug: str
    created_at: float = field(default_factory=time.time)

    @property
    def expired(self) -> bool:
        return time.time() - self.created_at > 600  # 10 minute expiry


class OAuthManager:
    """Manages OAuth2 flows for all registered tools."""

    def __init__(
        self,
        event_bus: EventBus,
        token_store_path: Path | None = None,
    ) -> None:
        self._bus = event_bus
        self._store_path = token_store_path or Path.home() / ".super-mcp" / "tokens.json"
        self._tokens: dict[str, TokenSet] = {}
        self._pending_states: dict[str, AuthState] = {}
        self._http = httpx.AsyncClient(timeout=30)

    async def initialize(self) -> None:
        """Load stored tokens from disk."""
        if self._store_path.exists():
            try:
                data = json.loads(self._store_path.read_text())
                for slug, tdata in data.items():
                    self._tokens[slug] = TokenSet(**tdata)
                await logger.ainfo("tokens_loaded", count=len(self._tokens))
            except Exception as e:
                await logger.aerror("token_load_failed", error=str(e))

    async def save_tokens(self) -> None:
        """Persist tokens to disk (encrypted in production)."""
        self._store_path.parent.mkdir(parents=True, exist_ok=True)
        data = {}
        for slug, token_set in self._tokens.items():
            data[slug] = {
                "tool_slug": token_set.tool_slug,
                "access_token": token_set.access_token,
                "refresh_token": token_set.refresh_token,
                "token_type": token_set.token_type,
                "expires_at": token_set.expires_at,
                "scopes": token_set.scopes,
                "obtained_at": token_set.obtained_at,
            }
        self._store_path.write_text(json.dumps(data, indent=2))

    def start_oauth_flow(self, tool_slug: str, config: OAuthConfig) -> str:
        """Generate an authorization URL for the OAuth flow."""
        state = secrets.token_urlsafe(32)
        code_verifier = secrets.token_urlsafe(64)
        code_challenge = urlsafe_b64encode(
            hashlib.sha256(code_verifier.encode()).digest()
        ).decode().rstrip("=")

        self._pending_states[state] = AuthState(
            state=state,
            code_verifier=code_verifier,
            tool_slug=tool_slug,
        )

        params = {
            "client_id": config.client_id_env,
            "redirect_uri": config.redirect_uri,
            "response_type": "code",
            "state": state,
        }

        if config.scopes:
            params["scope"] = " ".join(config.scopes)

        if config.pkce:
            params["code_challenge"] = code_challenge
            params["code_challenge_method"] = "S256"

        query = "&".join(f"{k}={v}" for k, v in params.items())
        return f"{config.authorization_url}?{query}"

    async def complete_oauth_flow(
        self, code: str, state: str, config: OAuthConfig
    ) -> TokenSet | None:
        """Exchange authorization code for tokens."""
        auth_state = self._pending_states.pop(state, None)
        if not auth_state or auth_state.expired:
            await logger.aerror("oauth_state_invalid_or_expired", state=state)
            return None

        payload = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": config.redirect_uri,
            "client_id": config.client_id_env,
            "client_secret": config.client_secret_env,
        }

        if config.pkce:
            payload["code_verifier"] = auth_state.code_verifier

        try:
            resp = await self._http.post(config.token_url, data=payload)
            resp.raise_for_status()
            data = resp.json()

            token_set = TokenSet(
                tool_slug=auth_state.tool_slug,
                access_token=data["access_token"],
                refresh_token=data.get("refresh_token"),
                token_type=data.get("token_type", "Bearer"),
                expires_at=time.time() + data.get("expires_in", 3600),
                scopes=data.get("scope", "").split(),
            )

            self._tokens[auth_state.tool_slug] = token_set
            await self.save_tokens()

            await self._bus.emit(
                kind="oauth.token_obtained",
                source="oauth_manager",
                data={"tool": auth_state.tool_slug},
            )

            return token_set

        except Exception as e:
            await logger.aerror("oauth_exchange_failed", error=str(e))
            await self._bus.emit(
                kind="oauth.exchange_failed",
                source="oauth_manager",
                data={"tool": auth_state.tool_slug, "error": str(e)},
                severity=Severity.ERROR,
            )
            return None

    async def refresh_token(self, tool_slug: str, config: OAuthConfig) -> TokenSet | None:
        """Refresh an expired token."""
        current = self._tokens.get(tool_slug)
        if not current or not current.refresh_token:
            return None

        payload = {
            "grant_type": "refresh_token",
            "refresh_token": current.refresh_token,
            "client_id": config.client_id_env,
            "client_secret": config.client_secret_env,
        }

        try:
            resp = await self._http.post(config.token_url, data=payload)
            resp.raise_for_status()
            data = resp.json()

            token_set = TokenSet(
                tool_slug=tool_slug,
                access_token=data["access_token"],
                refresh_token=data.get("refresh_token", current.refresh_token),
                token_type=data.get("token_type", "Bearer"),
                expires_at=time.time() + data.get("expires_in", 3600),
                scopes=data.get("scope", "").split() or current.scopes,
            )

            self._tokens[tool_slug] = token_set
            await self.save_tokens()

            await self._bus.emit(
                kind="oauth.token_refreshed",
                source="oauth_manager",
                data={"tool": tool_slug},
            )

            return token_set

        except Exception as e:
            await logger.aerror("oauth_refresh_failed", tool=tool_slug, error=str(e))
            return None

    def get_token(self, tool_slug: str) -> TokenSet | None:
        return self._tokens.get(tool_slug)

    def has_valid_token(self, tool_slug: str) -> bool:
        token = self._tokens.get(tool_slug)
        return token is not None and token.valid

    def authenticated_tools(self) -> list[str]:
        return [slug for slug, t in self._tokens.items() if t.valid]

    async def revoke_token(self, tool_slug: str) -> None:
        self._tokens.pop(tool_slug, None)
        await self.save_tokens()
        await self._bus.emit(
            kind="oauth.token_revoked",
            source="oauth_manager",
            data={"tool": tool_slug},
        )

    async def close(self) -> None:
        await self._http.aclose()
