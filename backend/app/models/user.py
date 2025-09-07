"""
Example SQLModel usage with the configured database setup.
"""

from typing import Optional
from sqlmodel import SQLModel, Field
from datetime import datetime


class User(SQLModel, table=True):
    """Example User model."""

    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(unique=True, index=True)
    username: str = Field(unique=True, index=True)
    full_name: Optional[str] = None
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None


class UserCreate(SQLModel):
    """User creation schema."""

    email: str
    username: str
    full_name: Optional[str] = None


class UserRead(SQLModel):
    """User read schema."""

    id: int
    email: str
    username: str
    full_name: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None


class UserUpdate(SQLModel):
    """User update schema."""

    email: Optional[str] = None
    username: Optional[str] = None
    full_name: Optional[str] = None
    is_active: Optional[bool] = None
