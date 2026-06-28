import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def _utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String, unique=True)
    name: Mapped[str] = mapped_column(String, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class Workspace(Base):
    __tablename__ = "workspaces"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String, unique=True)
    name: Mapped[str]
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    plan: Mapped[str] = mapped_column(default="free")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class ApiKey(Base):
    __tablename__ = "api_keys"
    __table_args__ = (Index("api_keys_prefix_idx", "key_prefix"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id"))
    key_hash: Mapped[str]
    key_prefix: Mapped[str]
    name: Mapped[str]
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class Deployment(Base):
    __tablename__ = "deployments"
    __table_args__ = (
        UniqueConstraint("workspace_id", "slug"),
        Index("deployments_storage_key_idx", "storage_key"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id"))
    slug: Mapped[str]
    content_type: Mapped[str]
    storage_key: Mapped[str]
    # "pending" until the artifact bytes land in storage, then "deployed". A
    # pending row reserves the slug but does not serve.
    status: Mapped[str] = mapped_column(String, default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    deployed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
