from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings, loaded from environment variables and an optional .env file."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    r2_account_id: str
    r2_access_key_id: str
    r2_secret_access_key: str
    r2_bucket_name: str = "undocking-artifacts"
    r2_public_url: str
    public_base_url: str = "http://localhost:8000"
    port: int = 8000

    # Serves /docs, /redoc, and /openapi.json when true (the default, for local
    # dev). Set to false in production so the API's schema isn't publicly
    # browsable.
    docs_enabled: bool = True

    # How long a presigned upload URL stays valid, in seconds (default 15 min).
    upload_url_expiry_seconds: int = 900

    # Shared secret for the internal R2 event webhook (POST /internal/r2-events).
    # The Cloudflare Queue consumer/Worker must send it in the
    # X-Undocking-Event-Secret header. Empty disables the webhook (returns 503).
    r2_event_secret: str = ""

    # Shared secret the undocking.io Next.js app attaches (X-Undocking-Proxy-Secret
    # header) to every request it proxies to /admin and /auth. Those two routers
    # reject anything else. Empty disables the check — the local-dev default, so
    # :8000 stays directly reachable without extra setup.
    proxy_shared_secret: str = ""

    # Dashboard auth (phase 2). The admin panel signs users in via OAuth; the
    # API runs the OAuth dance and issues an HttpOnly session cookie.
    #
    # session_secret signs the session cookie — override it with a long random
    # value in production. The default below exists only so tests and local dev
    # boot without extra setup.
    session_secret: str = "dev-insecure-session-secret-change-me"

    # Base URL of the dashboard (where users land after signing in).
    frontend_url: str = "http://localhost:3000"

    # Browser-facing base URL of this API. In dev the Next.js app proxies
    # /api/* to the API so the session cookie stays first-party, so this points
    # at the proxy. The OAuth redirect URI is built from it as
    # "{public_api_url}/auth/callback/{provider}".
    public_api_url: str = "http://localhost:3000/api"

    # OAuth provider credentials. A provider is only enabled when both its id
    # and secret are set, so you can run with GitHub only, Google only, or both.
    github_client_id: str = ""
    github_client_secret: str = ""
    google_client_id: str = ""
    google_client_secret: str = ""


settings = Settings()
