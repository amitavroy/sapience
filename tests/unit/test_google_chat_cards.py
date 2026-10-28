from app.core.google_chat_client import GoogleChatError
from app.services import google_chat
from app.services.google_chat import ClarificationCard
from tests.agent_helpers import FakeChat


class CardChat(FakeChat):
    def __init__(self, fail_update: bool = False) -> None:
        super().__init__()
        self.cards: list[tuple[str, str, list[dict]]] = []
        self.updates: list[tuple[str, str, list[dict] | None]] = []
        self.fail_update = fail_update

    async def create_card_message(self, space: str, text: str, cards_v2: list[dict]) -> str:
        self.cards.append((space, text, cards_v2))
        return f"{space}/messages/card"

    async def update_message(self, name: str, text: str, cards_v2: list[dict] | None) -> None:
        if self.fail_update:
            raise GoogleChatError("nope", 500)
        self.updates.append((name, text, cards_v2))


CARD = ClarificationCard("abc", "Which of these did you mean?", ["Billing", "Invoices"], "users/1")


async def test_send_card_has_option_buttons_and_none():
    chat = CardChat()

    name = await google_chat.send_card(chat, "spaces/AAA", CARD)

    assert name == "spaces/AAA/messages/card"
    _, text, cards = chat.cards[0]
    assert text == CARD.question
    buttons = cards[0]["card"]["sections"][0]["widgets"][1]["buttonList"]["buttons"]
    assert [b["text"] for b in buttons] == ["Billing", "Invoices", "None of these"]
    params = [{p["key"]: p["value"] for p in b["onClick"]["action"]["parameters"]} for b in buttons]
    assert [p["option"] for p in params] == ["0", "1", "none"]
    assert all(p["clarification_id"] == "abc" and p["asker"] == "users/1" for p in params)
    assert params[1]["label"] == "Invoices"


async def test_edit_card_replaces_cards_with_note():
    chat = CardChat()

    await google_chat.edit_card(chat, "spaces/AAA/messages/card", google_chat.SKIPPED_NOTE)

    assert chat.updates == [("spaces/AAA/messages/card", "This question was skipped.", None)]


async def test_edit_card_failure_is_swallowed():
    await google_chat.edit_card(CardChat(fail_update=True), "m", google_chat.EXPIRED_NOTE)
