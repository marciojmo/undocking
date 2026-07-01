-- Undocking API database schema (PostgreSQL).
--
-- The MVP has no management endpoints, so workspaces and API keys are seeded
-- directly. See the bottom of this file for a seeding example.

CREATE EXTENSION IF NOT EXISTS "pgcrypto";  -- for gen_random_uuid()

CREATE TABLE IF NOT EXISTS users (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email      TEXT NOT NULL UNIQUE,
    name       TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS workspaces (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slug       TEXT NOT NULL UNIQUE,
    name       TEXT NOT NULL,
    owner_id   UUID NOT NULL REFERENCES users (id),
    plan       TEXT NOT NULL DEFAULT 'free',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS api_keys (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL REFERENCES workspaces (id),
    key_hash     TEXT NOT NULL,
    key_prefix   TEXT NOT NULL,
    name         TEXT NOT NULL,
    revoked_at   TIMESTAMPTZ,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS api_keys_prefix_idx ON api_keys (key_prefix);

CREATE TABLE IF NOT EXISTS deployments (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL REFERENCES workspaces (id),
    slug         TEXT NOT NULL,
    content_type TEXT NOT NULL,
    storage_key  TEXT NOT NULL,
    status       TEXT NOT NULL DEFAULT 'pending',
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    deployed_at  TIMESTAMPTZ,
    deleted_at   TIMESTAMPTZ,
    CONSTRAINT deployments_workspace_slug_key UNIQUE (workspace_id, slug)
);

-- The R2 event webhook looks deployments up by storage_key.
CREATE INDEX IF NOT EXISTS deployments_storage_key_idx ON deployments (storage_key);

-- Seeding example -----------------------------------------------------------
--
-- 1. Pick a raw key that starts with "sk_live_", e.g.
--      sk_live_2b8f4c1e9a7d6f30  (use a securely random value in practice)
-- 2. key_prefix is the first 16 characters of the raw key.
-- 3. key_hash is the SHA-256 hex digest of the full raw key:
--      python -c "import hashlib,sys; print(hashlib.sha256(sys.argv[1].encode()).hexdigest())" sk_live_...
--
-- INSERT INTO users (email, name) VALUES ('owner@example.com', 'Owner')
--   RETURNING id;  -- use this id as owner_id below
--
-- INSERT INTO workspaces (slug, name, owner_id)
--   VALUES ('acme', 'Acme', '<owner-id>') RETURNING id;  -- use as workspace_id
--
-- INSERT INTO api_keys (workspace_id, key_hash, key_prefix, name)
--   VALUES ('<workspace-id>', '<sha256-hex>', 'sk_live_2b8f4c1e', 'default');
