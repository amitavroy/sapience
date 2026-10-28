from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator
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


class AppCommandMetadata(ChatModel):
    app_command_id: int  # Google sends it as a float (1.0)
    app_command_type: str  # SLASH_COMMAND


class AppCommandPayload(ChatModel):
    space: ChatSpace
    message: ChatMessage
    app_command_metadata: AppCommandMetadata


class ButtonClickedPayload(ChatModel):
    space: ChatSpace
    message: ChatMessage  # the card the button is on


class ChatPayload(ChatModel):
    user: ChatUser | None = None
    event_time: datetime | None = None
    message_payload: MessagePayload | None = None  # @mention; absent for e.g. added-to-space
    app_command_payload: AppCommandPayload | None = None  # slash command
    button_clicked_payload: ButtonClickedPayload | None = None  # a card button
    # not sent by Google inside `chat`: the router copies commonEventObject.parameters here for a
    # click, so the worker sees what the button carried
    action_parameters: dict[str, str] = {}


class CommonEventObject(ChatModel):
    parameters: dict[str, str] = {}  # a clicked button's action parameters


class GoogleChatEvent(ChatModel):
    authorization_event_object: AuthorizationEventObject
    common_event_object: CommonEventObject | None = None
    chat: ChatPayload | None = None


class SendMessageRequest(BaseModel):
    space: str = Field(pattern=r"^spaces/[A-Za-z0-9_-]+$", examples=["spaces/AAAAxxxx"])
    text: str = Field(min_length=1, max_length=8000)

    @field_validator("text")
    @classmethod
    def not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("text is blank")
        return v


class SendMessageResponse(BaseModel):
    name: str
