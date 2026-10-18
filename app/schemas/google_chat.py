from datetime import datetime

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class ChatModel(BaseModel):
    # Google sends camelCase and may add fields at any time, so keep unknown ones
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="allow")


class AuthorizationEventObject(ChatModel):
    system_id_token: str


class ChatUser(ChatModel):
    name: str
    display_name: str | None = None
    email: str | None = None
    type: str | None = None  # HUMAN | BOT


class ChatSpace(ChatModel):
    name: str
    display_name: str | None = None  # absent in a DM
    type: str | None = None


class ChatThread(ChatModel):
    name: str


class ChatMessage(ChatModel):
    name: str
    text: str = ""
    argument_text: str | None = None  # text after the @mention, with a leading space
    sender: ChatUser | None = None
    thread: ChatThread | None = None


class MessagePayload(ChatModel):
    space: ChatSpace
    message: ChatMessage


class ChatPayload(ChatModel):
    user: ChatUser | None = None
    event_time: datetime | None = None
    message_payload: MessagePayload | None = None  # absent for e.g. added-to-space events


class GoogleChatEvent(ChatModel):
    authorization_event_object: AuthorizationEventObject
    chat: ChatPayload | None = None
