from sqlalchemy.ext.asyncio import AsyncSession

from app.models.collection import Collection, CollectionMember, CollectionRole
from app.services import user as user_service


class OwnerNotFoundError(Exception):
    pass


async def get(db: AsyncSession, collection_id: int) -> Collection | None:
    return await db.get(Collection, collection_id)


async def exists(db: AsyncSession, collection_id: int) -> bool:
    return await get(db, collection_id) is not None


async def create_collection(
    db: AsyncSession, name: str, description: str | None = None, owner_email: str | None = None
) -> Collection:
    """Create a collection; with `owner_email`, the user becomes its owner."""
    owner = None
    if owner_email is not None:
        owner = await user_service.get_by_email(db, owner_email)
        if owner is None:
            raise OwnerNotFoundError(owner_email)
    collection = Collection(
        name=name, description=description, created_by_id=owner.id if owner else None
    )
    db.add(collection)
    await db.flush()
    if owner is not None:
        db.add(
            CollectionMember(
                collection_id=collection.id, user_id=owner.id, role=CollectionRole.OWNER
            )
        )
    await db.commit()
    return collection
