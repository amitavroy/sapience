from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.deps import CurrentUser
from app.core.google_chat_client import GoogleChatClient, get_google_chat_client
from app.schemas.google_chat import SendMessageRequest, SendMessageResponse
from app.services import google_chat as google_chat_service

router = APIRouter(prefix="/google-chat", tags=["google-chat"])

ChatClient = Annotated[GoogleChatClient, Depends(get_google_chat_client)]


@router.post("/messages", response_model=SendMessageResponse)
async def send_message(body: SendMessageRequest, user: CurrentUser, client: ChatClient) -> dict:
    """Testing aid: post a message to a space as the app."""
    name = await google_chat_service.send_message(client, body.space, body.text)
    return {"name": name}
