import asyncio
import json
import time
from dataclasses import dataclass
from pathlib import Path

import httpx
import jwt
from fastapi import Request

CHAT_API = "https://chat.googleapis.com/v1"
CHAT_BOT_SCOPE = "https://www.googleapis.com/auth/chat.bot"
TOKEN_LIFETIME = 3600
REFRESH_MARGIN = 60


class GoogleChatError(Exception):
    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


class GoogleChatNotConfiguredError(GoogleChatError):
    pass


@dataclass(frozen=True)
class ServiceAccountCredentials:
    client_email: str
    private_key: str
    private_key_id: str
    token_uri: str

    @classmethod
    def from_file(cls, path: str) -> "ServiceAccountCredentials":
        if not path:
            raise GoogleChatNotConfiguredError("GOOGLE_CHAT_CREDENTIALS_FILE is not set")
        try:
            # SYNC-EXCEPTION: small local file, read once per client
            data = json.loads(Path(path).read_text())
            return cls(
                client_email=data["client_email"],
                private_key=data["private_key"],
                private_key_id=data["private_key_id"],
                token_uri=data["token_uri"],
            )
        except (OSError, ValueError, KeyError, TypeError) as e:
            raise GoogleChatNotConfiguredError(
                f"unreadable credentials file: {type(e).__name__}"
            ) from e


def _error_message(r: httpx.Response) -> str:
    try:
        body = r.json()
        error = body["error"]
        # Chat nests error.message; the token endpoint uses error_description
        return error["message"] if isinstance(error, dict) else body.get("error_description", error)
    except (ValueError, KeyError, TypeError):
        return f"http {r.status_code}"


def _raise_for_status(r: httpx.Response) -> None:
    if not r.is_success:
        raise GoogleChatError(_error_message(r), r.status_code)


class GoogleChatClient:
    def __init__(self, http: httpx.AsyncClient, credentials_file: str) -> None:
        self._http = http
        self._credentials_file = credentials_file
        self._creds: ServiceAccountCredentials | None = None
        self._token: str | None = None
        self._expires_at = 0.0
        self._lock = asyncio.Lock()

    async def _post(
        self,
        url: str,
        *,
        token: str | None = None,
        json: dict | None = None,
        data: dict | None = None,
    ) -> httpx.Response:
        headers = {"Authorization": f"Bearer {token}"} if token else None
        try:
            return await self._http.post(url, json=json, data=data, headers=headers)
        except httpx.HTTPError as e:
            raise GoogleChatError(f"request failed: {type(e).__name__}") from e

    async def _access_token(self, *, force: bool = False) -> str:
        async with self._lock:
            if force or self._token is None or time.monotonic() >= self._expires_at:
                await self._mint()
            return self._token

    async def _mint(self) -> None:
        creds = self._creds = self._creds or ServiceAccountCredentials.from_file(
            self._credentials_file
        )
        now = int(time.time())
        assertion = jwt.encode(
            {
                "iss": creds.client_email,
                "scope": CHAT_BOT_SCOPE,
                "aud": creds.token_uri,
                "iat": now,
                "exp": now + TOKEN_LIFETIME,
            },
            creds.private_key,
            algorithm="RS256",
            headers={"kid": creds.private_key_id},
        )
        r = await self._post(
            creds.token_uri,
            data={
                "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                "assertion": assertion,
            },
        )
        _raise_for_status(r)
        try:
            body = r.json()
            self._token = body["access_token"]
        except (ValueError, KeyError) as e:
            raise GoogleChatError("token response had no access_token", r.status_code) from e
        self._expires_at = (
            time.monotonic() + body.get("expires_in", TOKEN_LIFETIME) - REFRESH_MARGIN
        )

    async def create_message(self, space: str, text: str) -> str:
        """Posts a message to the space as the app; returns its name (spaces/…/messages/…)."""
        url = f"{CHAT_API}/{space}/messages"
        r = await self._post(url, json={"text": text}, token=await self._access_token())
        if r.status_code == 401:
            r = await self._post(
                url, json={"text": text}, token=await self._access_token(force=True)
            )
        _raise_for_status(r)
        return r.json()["name"]


def get_google_chat_client(request: Request) -> GoogleChatClient:
    return request.app.state.google_chat_client
