import pytest
from sqlalchemy import delete, insert, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Collection, CollectionMember, CollectionRole, User


async def make_user(session: AsyncSession, email: str) -> User:
    user = User(name=email.split("@")[0], email=email, password_hash="x")
    session.add(user)
    await session.flush()
    return user


async def make_collection(session: AsyncSession, owner: User) -> Collection:
    collection = Collection(name="Handbook", created_by_id=owner.id)
    collection.members.append(CollectionMember(user_id=owner.id, role=CollectionRole.OWNER))
    session.add(collection)
    await session.flush()
    return collection


async def roles(session: AsyncSession, collection_id: int) -> dict[int, str]:
    rows = await session.execute(
        select(CollectionMember.user_id, CollectionMember.role).where(
            CollectionMember.collection_id == collection_id
        )
    )
    return {user_id: role for user_id, role in rows.all()}


async def test_collection_with_owner(db_session: AsyncSession):
    ann = await make_user(db_session, "ann@example.com")
    collection = await make_collection(db_session, ann)

    assert collection.created_by_id == ann.id
    assert await roles(db_session, collection.id) == {ann.id: "owner"}


async def test_add_second_member_defaults_to_viewer(db_session: AsyncSession):
    ann = await make_user(db_session, "ann@example.com")
    bob = await make_user(db_session, "bob@example.com")
    collection = await make_collection(db_session, ann)

    db_session.add(CollectionMember(collection_id=collection.id, user_id=bob.id))
    await db_session.flush()

    assert await roles(db_session, collection.id) == {ann.id: "owner", bob.id: "viewer"}


async def test_duplicate_membership_rejected(db_session: AsyncSession):
    ann = await make_user(db_session, "ann@example.com")
    collection = await make_collection(db_session, ann)

    with pytest.raises(IntegrityError):
        await db_session.execute(
            insert(CollectionMember).values(
                collection_id=collection.id, user_id=ann.id, role=CollectionRole.EDITOR
            )
        )


async def test_bad_role_rejected(db_session: AsyncSession):
    ann = await make_user(db_session, "ann@example.com")
    bob = await make_user(db_session, "bob@example.com")
    collection = await make_collection(db_session, ann)

    db_session.add(CollectionMember(collection_id=collection.id, user_id=bob.id, role="admin"))
    with pytest.raises(IntegrityError):
        await db_session.flush()


async def test_deleting_user_removes_memberships_and_nulls_creator(db_session: AsyncSession):
    ann = await make_user(db_session, "ann@example.com")
    bob = await make_user(db_session, "bob@example.com")
    collection = await make_collection(db_session, ann)
    db_session.add(CollectionMember(collection_id=collection.id, user_id=bob.id))
    await db_session.flush()
    collection_id, ann_id, bob_id = collection.id, ann.id, bob.id

    await db_session.execute(delete(User).where(User.id == ann_id))
    db_session.expire_all()

    assert await roles(db_session, collection_id) == {bob_id: "viewer"}
    created_by_id = await db_session.scalar(
        select(Collection.created_by_id).where(Collection.id == collection_id)
    )
    assert created_by_id is None
