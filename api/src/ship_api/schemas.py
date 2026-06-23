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
