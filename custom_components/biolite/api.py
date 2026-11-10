"""Thin client for BioLite's backend REST API (built on ESP RainMaker).

There is no public API documentation for this -- the base URL and
endpoints were recovered by extracting strings from the BioLite app's
Flutter binary, and the request/response shapes were confirmed by making
real calls with a real account. See biolite_api_probe.py for the
exploratory script this was derived from.
"""
from __future__ import annotations

import base64
import json
import logging
import time

import aiohttp

from .const import BASE_URL, LOGIN_PATH, NODES_PATH, PARAMS_PATH, STATUS_PATH

_LOGGER = logging.getLogger(__name__)


class BioliteApiError(Exception):
    """Generic BioLite API error."""


class BioliteAuthError(BioliteApiError):
    """Raised when login fails (bad credentials)."""


# Re-login this many seconds before the token's actual "exp" claim, so a
# request that's in flight right as the token expires doesn't race a 401.
TOKEN_EXPIRY_MARGIN = 30


def _jwt_exp(token: str) -> float | None:
    """Return a JWT's "exp" claim (Unix timestamp), without verifying it.

    We only need to know when BioLite's own backend will reject this
    token -- the signature itself is irrelevant here, since we never
    trust the token's claims for anything security-sensitive, only for
    scheduling our own next login call.
    """
    try:
        payload_segment = token.split(".")[1]
        padded = payload_segment + "=" * (-len(payload_segment) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded))
        return payload.get("exp")
    except (IndexError, ValueError, TypeError):
        return None


class BioliteApiClient:
    """Handles authentication and requests against BioLite's cloud API."""

    def __init__(self, session: aiohttp.ClientSession, email: str, password: str) -> None:
        self._session = session
        self._email = email
        self._password = password
        self._access_token: str | None = None
        self._id_token: str | None = None
        self._refresh_token: str | None = None
        self._token_obtained_at: float = 0.0

    async def _login(self) -> None:
        """Authenticate with email/password and cache the returned tokens."""
        async with self._session.post(
            f"{BASE_URL}{LOGIN_PATH}",
            json={"user_name": self._email, "password": self._password},
        ) as resp:
            if resp.status != 200:
                raise BioliteAuthError(f"Login failed with status {resp.status}")
            body = await resp.json()

        self._access_token = body.get("accesstoken")
        self._id_token = body.get("idtoken")
        self._refresh_token = body.get("refreshtoken")
        self._token_obtained_at = time.monotonic()
        if not self._access_token:
            raise BioliteAuthError("Login response did not include an accesstoken")

    async def _ensure_token(self) -> None:
        """Log in if we have no token yet, or if it's at/past expiry.

        Reads the real "exp" claim out of the access token itself rather
        than guessing a lifetime. Falls back to a fixed-age heuristic only
        if a token somehow isn't a decodable JWT (shouldn't happen against
        this API, but better than crashing a poll cycle over it).
        """
        if self._access_token is None:
            await self._login()
            return

        exp = _jwt_exp(self._access_token)
        if exp is not None:
            if time.time() >= exp - TOKEN_EXPIRY_MARGIN:
                await self._login()
            return

        # No usable exp claim -- fall back to a conservative fixed age.
        if time.monotonic() - self._token_obtained_at >= 50 * 60:
            await self._login()

    async def _request(self, method: str, path: str, **kwargs) -> dict:
        await self._ensure_token()
        headers = {"Authorization": self._access_token}
        async with self._session.request(
            method, f"{BASE_URL}{path}", headers=headers, **kwargs
        ) as resp:
            if resp.status == 401:
                # Token rejected outright (not just expired-by-our-clock) --
                # force a fresh login and retry exactly once.
                await self._login()
                headers = {"Authorization": self._access_token}
                async with self._session.request(
                    method, f"{BASE_URL}{path}", headers=headers, **kwargs
                ) as retry_resp:
                    retry_resp.raise_for_status()
                    return await retry_resp.json()
            resp.raise_for_status()
            return await resp.json()

    async def async_get_node_id(self) -> str:
        """Return this account's single BioLite node ID."""
        body = await self._request("GET", NODES_PATH)
        nodes = body.get("nodes") or []
        if not nodes:
            raise BioliteApiError("Account has no BioLite nodes")
        return nodes[0]

    async def async_get_status(self, node_id: str) -> dict:
        return await self._request("GET", STATUS_PATH, params={"node_id": node_id})

    async def async_get_params(self, node_id: str) -> dict:
        return await self._request("GET", PARAMS_PATH, params={"node_id": node_id})
