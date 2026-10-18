import asyncio
from datetime import UTC, datetime, timedelta

import jwt
from pwdlib import PasswordHash

from app.core.config import settings

ALGORITHM = "HS256"

_hasher = PasswordHash.recommended()


async def hash_password(password: str) -> str:
    # SYNC-EXCEPTION: argon2 hashing is CPU-bound; run in a worker thread (argon2 releases the GIL)
    return await asyncio.to_thread(_hasher.hash, password)


async def verify_password(password: str, password_hash: str) -> bool:
    # SYNC-EXCEPTION: argon2 verification is CPU-bound; run in a worker thread
    return await asyncio.to_thread(_hasher.verify, password, password_hash)


def create_token(user_id: int, expires_minutes: int | None = None) -> str:
    minutes = settings.access_token_expire_minutes if expires_minutes is None else expires_minutes
    exp = datetime.now(UTC) + timedelta(minutes=minutes)
    return jwt.encode({"sub": str(user_id), "exp": exp}, settings.secret_key, algorithm=ALGORITHM)


def decode_token(token: str) -> int | None:
    """Return the user id, or None if the token is invalid or expired."""
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
        return int(payload["sub"])
    except (jwt.InvalidTokenError, KeyError, ValueError):
        return None
