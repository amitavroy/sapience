from fastapi import APIRouter

from app.core.deps import DbSession
from app.services import health as health_service

router = APIRouter(tags=["health"])


@router.get("/health")
async def health(db: DbSession) -> dict[str, str]:
    await health_service.ping_db(db)
    return {"status": "ok", "database": "ok"}
