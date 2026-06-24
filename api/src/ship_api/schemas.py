from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class DeployRequest(BaseModel):
    content: str = Field(min_length=1, max_length=5_000_000)
    content_type: Literal["html", "markdown"]
    slug: str | None = Field(default=None, min_length=1, max_length=64)


class DeployResponse(BaseModel):
    id: str
    url: str


class DeploymentItem(BaseModel):
    id: str
    slug: str
    content_type: str
    created_at: datetime
    url: str


# --- Dashboard (phase 2) ---------------------------------------------------


class ProviderList(BaseModel):
    providers: list[str]


class UserResponse(BaseModel):
    id: str
    email: str
    name: str


class WorkspaceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=64)


class WorkspaceResponse(BaseModel):
    id: str
    slug: str
    name: str
    plan: str
    created_at: datetime


class ApiKeyResponse(BaseModel):
    id: str
    name: str
    key_prefix: str
    created_at: datetime
    revoked_at: datetime | None


class ApiKeyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=64)


class ApiKeyCreated(ApiKeyResponse):
    """Returned only at creation time; ``key`` is the raw token, shown once."""

    key: str
