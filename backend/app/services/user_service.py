"""
User service for handling user-related database operations.
"""

from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlmodel import select as sqlmodel_select
from app.models.user import User, UserCreate, UserUpdate


class UserService:
    """Service class for user-related operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_user(self, user_data: UserCreate) -> User:
        """Create a new user."""
        # Check if user already exists
        existing_user = await self._get_user_by_email(user_data.email)
        if existing_user:
            raise ValueError("Email already registered")

        # Create new user
        user = User(**user_data.dict())
        self.session.add(user)
        await self.session.commit()
        await self.session.refresh(user)

        return user

    async def get_all_users(self) -> List[User]:
        """Get all users."""
        result = await self.session.execute(sqlmodel_select(User))
        users = result.scalars().all()
        return users

    async def get_user_by_id(self, user_id: int) -> User:
        """Get a specific user by ID."""
        result = await self.session.execute(
            sqlmodel_select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()

        if not user:
            raise ValueError("User not found")

        return user

    async def update_user(self, user_id: int, user_data: UserUpdate) -> User:
        """Update a user."""
        user = await self.get_user_by_id(
            user_id
        )  # This will raise ValueError if not found

        # Update user fields
        user_dict = user_data.dict(exclude_unset=True)
        for field, value in user_dict.items():
            setattr(user, field, value)

        self.session.add(user)
        await self.session.commit()
        await self.session.refresh(user)

        return user

    async def delete_user(self, user_id: int) -> None:
        """Delete a user."""
        user = await self.get_user_by_id(
            user_id
        )  # This will raise ValueError if not found

        await self.session.delete(user)
        await self.session.commit()

    async def _get_user_by_email(self, email: str) -> Optional[User]:
        """Get a user by email (private helper method)."""
        result = await self.session.execute(
            sqlmodel_select(User).where(User.email == email)
        )
        return result.scalar_one_or_none()
