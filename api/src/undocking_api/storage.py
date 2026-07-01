import asyncio

import boto3

from .config import settings

_client = boto3.client(
    "s3",
    region_name="auto",
    endpoint_url=f"https://{settings.r2_account_id}.r2.cloudflarestorage.com",
    aws_access_key_id=settings.r2_access_key_id,
    aws_secret_access_key=settings.r2_secret_access_key,
)


def _upload(key: str, content: str | bytes, content_type: str) -> None:
    body = content if isinstance(content, bytes) else content.encode()
    _client.put_object(
        Bucket=settings.r2_bucket_name,
        Key=key,
        Body=body,
        ContentType=content_type,
        CacheControl="public, max-age=31536000, immutable",
    )


def _download(key: str) -> bytes | None:
    try:
        res = _client.get_object(Bucket=settings.r2_bucket_name, Key=key)
        return res["Body"].read()
    except _client.exceptions.NoSuchKey:
        return None


def _head_etag(key: str) -> str | None:
    try:
        res = _client.head_object(Bucket=settings.r2_bucket_name, Key=key)
        return res["ETag"]
    except _client.exceptions.ClientError:
        return None


def generate_upload_url(key: str, content_type: str, expires_in: int) -> str:
    """Returns a presigned URL the caller can PUT raw artifact bytes to.

    Signing is a local operation (no network round-trip), so this stays
    synchronous. The ``ContentType`` is pinned in the presigned URL params so
    callers must send a matching ``Content-Type`` header on the PUT.

    Args:
        key: The object key the upload will be stored under.
        content_type: The MIME type of the artifact being uploaded.
        expires_in: How long the URL stays valid, in seconds.

    Returns:
        A presigned ``PUT`` URL.
    """
    return _client.generate_presigned_url(
        "put_object",
        Params={
            "Bucket": settings.r2_bucket_name,
            "Key": key,
            "ContentType": content_type,
        },
        ExpiresIn=expires_in,
    )


async def upload_artifact(key: str, content: str | bytes, content_type: str) -> None:
    """Uploads artifact content to storage under ``key`` with the given MIME type."""
    await asyncio.get_running_loop().run_in_executor(None, _upload, key, content, content_type)


async def download_artifact(key: str) -> bytes | None:
    """Returns the raw bytes stored under ``key``, or None if it does not exist."""
    return await asyncio.get_running_loop().run_in_executor(None, _download, key)


async def head_etag(key: str) -> str | None:
    """Returns the ETag of the object at ``key``, or None if it does not exist."""
    return await asyncio.get_running_loop().run_in_executor(None, _head_etag, key)
