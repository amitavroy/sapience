from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.deps import CurrentUser
from app.core.google_chat_client import (
    GoogleChatClient,
    GoogleChatError,
    GoogleChatNotConfiguredError,
    get_google_chat_client,
)
from app.core.logger import logger
from app.schemas.google_chat import SendMessageRequest, SendMessageResponse
from app.services import google_chat as google_chat_service

router = APIRouter(prefix="/google-chat", tags=["google-chat"])

ChatClient = Annotated[GoogleChatClient, Depends(get_google_chat_client)]


@router.post("/messages", response_model=SendMessageResponse)
async def send_message(body: SendMessageRequest, user: CurrentUser, client: ChatClient) -> dict:
    """Testing aid: post a message to a space as the app."""
    try:
        name = await google_chat_service.send_message(client, body.space, body.text)
    except GoogleChatNotConfiguredError as e:
        logger.warning(f"google chat send not configured: {e}")
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "Google Chat sending is not configured"
        ) from None
    except GoogleChatError as e:
        logger.warning(f"google chat send failed status={e.status}: {e}")
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, f"Google Chat rejected the message ({e.status})"
        ) from None
    return {"name": name}
