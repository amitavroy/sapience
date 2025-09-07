"""
User API endpoints using the user service.
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from config import get_session
from app.models.user import User, UserCreate, UserRead, UserUpdate
from app.services.user_service import UserService

router = APIRouter(prefix="/users", tags=["users"])


@router.post("/", response_model=UserRead)
async def create_user(
    user_data: UserCreate, session: AsyncSession = Depends(get_session)
):
    """Create a new user."""
    try:
        user_service = UserService(session)
        user = await user_service.create_user(user_data)
        return user
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/", response_model=List[UserRead])
async def get_users(session: AsyncSession = Depends(get_session)):
    """Get all users."""
    user_service = UserService(session)
    users = await user_service.get_all_users()
    return users


@router.get("/{user_id}", response_model=UserRead)
async def get_user(user_id: int, session: AsyncSession = Depends(get_session)):
    """Get a specific user by ID."""
    try:
        user_service = UserService(session)
        user = await user_service.get_user_by_id(user_id)
        return user
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.put("/{user_id}", response_model=UserRead)
async def update_user(
    user_id: int, user_data: UserUpdate, session: AsyncSession = Depends(get_session)
):
    """Update a user."""
    try:
        user_service = UserService(session)
        user = await user_service.update_user(user_id, user_data)
        return user
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/{user_id}")
async def delete_user(user_id: int, session: AsyncSession = Depends(get_session)):
    """Delete a user."""
    try:
        user_service = UserService(session)
        await user_service.delete_user(user_id)
        return {"message": "User deleted successfully"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
