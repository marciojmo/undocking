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


def _upload(key: str, html: str) -> None:
    _client.put_object(
        Bucket=settings.r2_bucket_name,
        Key=key,
        Body=html.encode(),
        ContentType="text/html; charset=utf-8",
        CacheControl="public, max-age=31536000, immutable",
    )


def _download(key: str) -> str | None:
    try:
        res = _client.get_object(Bucket=settings.r2_bucket_name, Key=key)
        return res["Body"].read().decode()
    except _client.exceptions.NoSuchKey:
        return None


async def upload_artifact(key: str, html: str) -> None:
    """Uploads rendered HTML to object storage under ``key``."""
    await asyncio.get_running_loop().run_in_executor(None, _upload, key, html)


async def download_artifact(key: str) -> str | None:
    """Returns the HTML stored under ``key``, or None if it does not exist."""
    return await asyncio.get_running_loop().run_in_executor(None, _download, key)
