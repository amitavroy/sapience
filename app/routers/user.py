from fastapi import APIRouter

from app.core.deps import CurrentUser
from app.models.user import User
from app.schemas.user import UserRead

router = APIRouter(tags=["user"])


@router.get("/user", response_model=UserRead)
async def read_current_user(user: CurrentUser) -> User:
    return user
