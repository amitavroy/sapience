from fastapi import APIRouter, HTTPException, status

from app.core.deps import DbSession
from app.core.security import create_token
from app.schemas.auth import LoginRequest, Token
from app.schemas.user import UserCreate, UserRead
from app.services import user as user_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def register(data: UserCreate, db: DbSession) -> UserRead:
    try:
        return await user_service.register_user(db, data)
    except user_service.EmailTakenError:
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered") from None


@router.post("/login", response_model=Token)
async def login(data: LoginRequest, db: DbSession) -> Token:
    user = await user_service.authenticate(db, data.email, data.password)
    if user is None:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return Token(access_token=create_token(user.id))
