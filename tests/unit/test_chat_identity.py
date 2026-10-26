import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.user import User
from app.services import user as user_service

CHAT_ID = "users/1001"


@pytest.fixture(autouse=True)
def allowed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "google_chat_allowed_email_domains", "example.com")


async def add_user(db: AsyncSession, email: str, **fields) -> User:
    user = User(name="Ann", email=email, password_hash="x", **fields)
    db.add(user)
    await db.commit()
    return user


async def user_count(db: AsyncSession) -> int:
    return await db.scalar(select(func.count()).select_from(User))


async def resolve(db: AsyncSession, email: str | None, chat_id: str = CHAT_ID) -> int | None:
    return await user_service.resolve_chat_user(db, chat_id, email, "Ann Example")


async def test_linked_chat_id_returns_its_user(db_session: AsyncSession) -> None:
    user = await add_user(db_session, "ann@example.com", google_chat_user_id=CHAT_ID)

    # the event's email is not consulted once the Chat id is linked
    assert await resolve(db_session, None) == user.id


async def test_first_contact_with_a_known_email_links_it(db_session: AsyncSession) -> None:
    user = await add_user(db_session, "ann@example.com")

    assert await resolve(db_session, "Ann@Example.COM") == user.id

    await db_session.refresh(user)
    assert user.google_chat_user_id == CHAT_ID
    assert await user_count(db_session) == 1


async def test_unknown_email_creates_a_user_with_no_password(db_session: AsyncSession) -> None:
    user_id = await resolve(db_session, "New@example.com")

    user = await db_session.get(User, user_id)
    assert (user.email, user.name, user.password_hash) == ("new@example.com", "Ann Example", None)
    assert user.google_chat_user_id == CHAT_ID
    assert await user_service.authenticate(db_session, "new@example.com", "") is None


async def test_second_call_for_the_same_sender_creates_no_second_user(
    db_session: AsyncSession,
) -> None:
    first = await resolve(db_session, "new@example.com")

    assert await resolve(db_session, "new@example.com") == first
    assert await user_count(db_session) == 1


async def test_email_linked_to_another_chat_id_is_not_relinked(db_session: AsyncSession) -> None:
    user = await add_user(db_session, "ann@example.com", google_chat_user_id="users/other")

    assert await resolve(db_session, "ann@example.com") is None

    await db_session.refresh(user)
    assert user.google_chat_user_id == "users/other"


async def test_inactive_user_is_rejected(db_session: AsyncSession) -> None:
    await add_user(db_session, "ann@example.com", google_chat_user_id=CHAT_ID, is_active=False)

    assert await resolve(db_session, "ann@example.com") is None


async def test_no_link_and_no_email_creates_nothing(db_session: AsyncSession) -> None:
    assert await resolve(db_session, None) is None
    assert await user_count(db_session) == 0


@pytest.mark.parametrize(
    ("setting", "email"),
    [
        ("example.com", "ann@other.com"),
        ("example.com", "ann@sub.example.com"),
        ("", "ann@example.com"),
    ],
    ids=["other-domain", "subdomain", "empty-setting"],
)
async def test_email_outside_the_allowed_domains_creates_and_links_nothing(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch, setting: str, email: str
) -> None:
    monkeypatch.setattr(settings, "google_chat_allowed_email_domains", setting)
    known = await add_user(db_session, "ann@example.com")

    assert await resolve(db_session, email) is None

    await db_session.refresh(known)
    assert known.google_chat_user_id is None
    assert await user_count(db_session) == 1


async def test_domain_match_ignores_case_and_parses_a_spaced_list(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "google_chat_allowed_email_domains", " example.org , EXAMPLE.com")

    assert await resolve(db_session, "ann@Example.Com") is not None


async def test_linked_user_is_cut_off_when_their_domain_is_removed(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    await add_user(db_session, "ann@example.com", google_chat_user_id=CHAT_ID)
    monkeypatch.setattr(settings, "google_chat_allowed_email_domains", "example.org")

    assert await resolve(db_session, "ann@example.com") is None


async def test_lost_race_on_first_contact_reads_the_row_again(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    # a concurrent first message created the user between our lookup and our insert
    winner = await add_user(db_session, "ann@example.com", google_chat_user_id=CHAT_ID)
    lookups = iter([None])
    real = user_service._by_chat_id

    async def first_lookup_misses(db: AsyncSession, chat_user_id: str) -> User | None:
        return next(lookups, None) or await real(db, chat_user_id)

    monkeypatch.setattr(user_service, "_by_chat_id", first_lookup_misses)
    monkeypatch.setattr(user_service, "get_by_email", lambda db, email: _none())

    assert await resolve(db_session, "ann@example.com") == winner.id
    assert await user_count(db_session) == 1


async def _none() -> None:
    return None
