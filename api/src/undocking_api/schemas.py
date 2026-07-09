from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

INLINE_CONTENT_TYPES = frozenset({
    "text/html",
    "text/markdown",
    "text/plain",
    "text/csv",
    "application/json",
    "image/svg+xml",
})

UPLOAD_CONTENT_TYPES = INLINE_CONTENT_TYPES | frozenset({
    "image/png",
    "image/jpeg",
    "image/gif",
    "image/webp",
    "application/pdf",
})

_INLINE_LIST = ", ".join(sorted(INLINE_CONTENT_TYPES))
_UPLOAD_LIST = ", ".join(sorted(UPLOAD_CONTENT_TYPES))


class DeployRequest(BaseModel):
    content_type: str
    slug: str | None = Field(default=None, min_length=1, max_length=64)
    # Inline content for the deploy path. The artifact is live immediately. Use
    # POST /v1/uploads for large files or binary types.
    content: str = Field(min_length=1, max_length=1_000_000)

    @field_validator("content_type")
    @classmethod
    def validate_content_type(cls, v: str) -> str:
        if v not in INLINE_CONTENT_TYPES:
            raise ValueError(
                f"Unsupported content_type '{v}'. "
                f"Inline deploy accepts: {_INLINE_LIST}. "
                "For binary files (image/png, image/jpeg, application/pdf, etc.) use POST /v1/uploads."
            )
        return v


class DeployResponse(BaseModel):
    id: str
    url: str
    # Inline deploys are live immediately, so this is always "deployed".
    status: str


class UploadReserveRequest(BaseModel):
    content_type: str
    slug: str | None = Field(default=None, min_length=1, max_length=64)

    @field_validator("content_type")
    @classmethod
    def validate_content_type(cls, v: str) -> str:
        if v not in UPLOAD_CONTENT_TYPES:
            raise ValueError(
                f"Unsupported content_type '{v}'. "
                f"Accepted: {_UPLOAD_LIST}."
            )
        return v


class UploadReserveResponse(BaseModel):
    id: str
    url: str
    upload_url: str
    expires_in: int
    method: str = "PUT"
    # The MIME type to send as Content-Type header on the PUT request.
    content_type: str
    # Always "pending": the row goes live once the upload lands.
    status: str = "pending"


class R2Event(BaseModel):
    """A permissive view of an R2 event-notification record.

    R2 / Cloudflare Queue payloads vary by source and version, so only the
    fields we act on are modeled and everything else is ignored. The object key
    may arrive under ``object.key``; the action under ``action`` or ``eventType``.
    """

    model_config = ConfigDict(extra="ignore")

    object: dict | None = None
    action: str | None = None
    eventType: str | None = None  # noqa: N815 - matches R2's camelCase field

    def object_key(self) -> str | None:
        if self.object is None:
            return None
        key = self.object.get("key")
        return key if isinstance(key, str) else None

    def action_name(self) -> str | None:
        return self.action or self.eventType


class DeploymentItem(BaseModel):
    id: str
    slug: str
    content_type: str
    status: str
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


class WorkspaceUpdate(BaseModel):
    slug: str = Field(min_length=1, max_length=64, pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$")


class WorkspaceResponse(BaseModel):
    id: str
    slug: str
    name: str
    plan: str
    created_at: datetime


class ApiKeyResponse(BaseModel):
    id: str
    name: str | None
    key_prefix: str
    created_at: datetime
    revoked_at: datetime | None


class ApiKeyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=64)


class ApiKeyCreated(ApiKeyResponse):
    """Returned only at creation time; ``key`` is the raw token, shown once."""

    key: str


class AgentConnectResponse(BaseModel):
    """Returned when a workspace and its first API key are created together."""

    workspace: WorkspaceResponse
    key: ApiKeyCreated
