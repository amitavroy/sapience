from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.google_auth import GoogleTokenVerifier, InvalidGoogleTokenError, get_google_verifier
from app.core.logger import logger
from app.core.security import decode_token
from app.db.session import async_session_factory
from app.models.user import User
from app.schemas.google_chat import GoogleChatEvent
from app.services import user as user_service

bearer_scheme = HTTPBearer(auto_error=False)


async def get_db() -> AsyncIterator[AsyncSession]:
    async with async_session_factory() as session:
        yield session


DbSession = Annotated[AsyncSession, Depends(get_db)]


Creds = Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)]


async def get_current_user(creds: Creds, db: DbSession) -> User:
    user_id = decode_token(creds.credentials) if creds else None
    user = await user_service.get(db, user_id) if user_id is not None else None
    if user is None or not user.is_active:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


Verifier = Annotated[GoogleTokenVerifier, Depends(get_google_verifier)]


async def get_verified_chat_event(request: Request, verifier: Verifier) -> GoogleChatEvent:
    try:
        event = GoogleChatEvent.model_validate(await request.json())
        await verifier.verify(
            event.authorization_event_object.system_id_token,
            audience=settings.google_chat_audience,
            email=settings.google_chat_service_account_email,
        )
    except (ValueError, ValidationError, InvalidGoogleTokenError) as e:
        # 401 for a malformed body too, so callers learn nothing about the expected shape
        logger.warning(f"google chat event rejected: {e}")
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid Google Chat request") from None
    return event


VerifiedChatEvent = Annotated[GoogleChatEvent, Depends(get_verified_chat_event)]
