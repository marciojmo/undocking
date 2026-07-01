import re
import secrets
import string

_ALPHABET = string.ascii_lowercase + string.digits


def generate_slug(length: int = 10) -> str:
    """Returns a random lowercase alphanumeric slug of the given length."""
    return "".join(secrets.choice(_ALPHABET) for _ in range(length))


def sanitize_slug(raw: str) -> str:
    """Normalizes caller-supplied text into a URL-safe slug.

    Lowercases, replaces runs of disallowed characters with single hyphens,
    trims leading/trailing hyphens, and caps the length at 64 characters.
    """
    slug = re.sub(r"[^a-z0-9-]", "-", raw.lower())
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug[:64]
