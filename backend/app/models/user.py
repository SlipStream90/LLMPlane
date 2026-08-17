"""User model for OAuth authentication.

Users authenticate via GitHub or Google OAuth and receive a JWT session token.
The User model stores profile info from the OAuth provider and links to the
default organization/project for API key generation.
"""

from __future__ import annotations

import uuid

from sqlalchemy import String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "user"
    __table_args__ = (
        UniqueConstraint("provider", "provider_user_id", name="uq_user_provider_id"),
    )

    email: Mapped[str] = mapped_column(String(255), index=True)
    name: Mapped[str | None] = mapped_column(String(255))
    avatar_url: Mapped[str | None] = mapped_column(String(1024))
    provider: Mapped[str] = mapped_column(String(50))  # "github" or "google"
    provider_user_id: Mapped[str] = mapped_column(String(255))
    last_login_at: Mapped[uuid.UUID | None] = mapped_column(
        String(36), nullable=True
    )  # ISO timestamp stored as string for simplicity

    # Optional link to the default project for API key scoping
    default_project_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )

    def __repr__(self) -> str:
        return f"<User {self.email} ({self.provider})>"
