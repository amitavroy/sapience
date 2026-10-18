import asyncio
import re
import time

import httpx
import jwt
from fastapi import Request

GOOGLE_CERTS_URL = "https://www.googleapis.com/oauth2/v3/certs"
GOOGLE_ISSUER = "https://accounts.google.com"
DEFAULT_MAX_AGE = 3600


class InvalidGoogleTokenError(Exception):
    pass


def _max_age(cache_control: str | None) -> int:
    match = re.search(r"max-age=(\d+)", cache_control or "")
    return int(match.group(1)) if match else DEFAULT_MAX_AGE


class GoogleTokenVerifier:
    def __init__(self, http: httpx.AsyncClient) -> None:
        self._http = http
        self._keys: dict[str, jwt.PyJWK] = {}
        self._expires_at = 0.0
        self._lock = asyncio.Lock()

    async def _refresh(self) -> None:
        r = await self._http.get(GOOGLE_CERTS_URL)
        r.raise_for_status()
        self._keys = {k["kid"]: jwt.PyJWK(k) for k in r.json()["keys"]}
        self._expires_at = time.monotonic() + _max_age(r.headers.get("cache-control"))

    async def _key(self, kid: str, *, force: bool = False) -> jwt.PyJWK | None:
        async with self._lock:
            if force or time.monotonic() >= self._expires_at:
                await self._refresh()
            return self._keys.get(kid)

    async def verify(self, token: str, *, audience: str, email: str) -> dict:
        if not audience or not email:
            raise InvalidGoogleTokenError("google chat verification not configured")
        try:
            kid = jwt.get_unverified_header(token).get("kid")
            if not kid:
                raise InvalidGoogleTokenError("token has no kid")
            key = await self._key(kid) or await self._key(kid, force=True)
            if key is None:
                raise InvalidGoogleTokenError(f"unknown kid {kid}")
            claims = jwt.decode(
                token,
                key,
                algorithms=["RS256"],
                audience=audience,
                issuer=GOOGLE_ISSUER,
                options={"require": ["exp", "iss", "aud"]},
            )
        except (jwt.InvalidTokenError, httpx.HTTPError, KeyError, ValueError) as e:
            raise InvalidGoogleTokenError(str(e)) from e
        if claims.get("email_verified") is not True or claims.get("email") != email:
            raise InvalidGoogleTokenError("unexpected token email")
        return claims


def get_google_verifier(request: Request) -> GoogleTokenVerifier:
    return request.app.state.google_verifier
