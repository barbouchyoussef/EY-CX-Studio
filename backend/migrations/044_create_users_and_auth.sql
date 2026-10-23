-- Identity foundation: users, invites, and refresh tokens.
-- The app had no concept of a person before this; every record was globally visible.
-- This migration adds the primitives auth and (later) per-record ownership hang off.

CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(320) NOT NULL UNIQUE,          -- stored normalised to lowercase by the app
    full_name VARCHAR(200) NOT NULL,
    password_hash VARCHAR(255),                  -- NULL until an invite is accepted
    role VARCHAR(20) NOT NULL DEFAULT 'consultant',  -- 'admin' | 'consultant'
    status VARCHAR(20) NOT NULL DEFAULT 'pending',   -- 'pending' | 'active' | 'disabled'
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

-- One row per outstanding invitation. The token is single-use (accepted_at) and expiring.
CREATE TABLE IF NOT EXISTS invites (
    token VARCHAR(64) PRIMARY KEY,               -- secrets.token_urlsafe(32), unguessable
    email VARCHAR(320) NOT NULL,
    role VARCHAR(20) NOT NULL DEFAULT 'consultant',
    invited_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    accepted_at TIMESTAMPTZ,                      -- set once; a second accept is rejected
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_invites_email ON invites(email);

-- Refresh-token registry. We never store the raw token -- jti is its SHA-256 hash, so a DB
-- leak yields nothing replayable. family_id groups a login's rotation chain: replaying an
-- already-rotated token revokes the whole family (theft detection).
CREATE TABLE IF NOT EXISTS refresh_tokens (
    jti VARCHAR(64) PRIMARY KEY,                  -- sha256 hex of the raw cookie value
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    family_id VARCHAR(64) NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    revoked_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_refresh_tokens_user_id ON refresh_tokens(user_id);
CREATE INDEX IF NOT EXISTS idx_refresh_tokens_family_id ON refresh_tokens(family_id);
