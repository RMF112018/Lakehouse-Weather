-- INERT PROPOSAL ONLY. Do not execute as an independent migration chain.
-- my-pa database owner must adopt into canonical Alembic history after review.
-- Target verified logical database my_pa, isolated nonproduction first.
-- Role creation and grants deliberately omitted: owner must provision a dedicated
-- non-owner, non-superuser role restricted to this schema and tables.
CREATE SCHEMA weather;
CREATE TABLE weather.locations (
    id text PRIMARY KEY,
    metadata jsonb NOT NULL CHECK (jsonb_typeof(metadata) = 'object')
);
CREATE TABLE weather.stations (
    id text PRIMARY KEY,
    location_id text NOT NULL REFERENCES weather.locations(id),
    metadata jsonb NOT NULL CHECK (jsonb_typeof(metadata) = 'object')
);
CREATE TABLE weather.observations (
    station_id text NOT NULL REFERENCES weather.stations(id),
    observed_at timestamptz NOT NULL,
    measurements jsonb NOT NULL CHECK (jsonb_typeof(measurements) = 'object'),
    received_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (station_id, observed_at)
);
CREATE TABLE weather.forecast_cache (
    location_id text PRIMARY KEY REFERENCES weather.locations(id),
    payload jsonb NOT NULL CHECK (jsonb_typeof(payload) = 'object')
);
-- No retention deletion: observations remain until owner-approved policy exists.
-- Existing composite PK supports station/time history and latest queries.
CREATE TABLE weather.auth_users (
    id integer PRIMARY KEY CHECK (id = 1),
    email text NOT NULL,
    password_hash text NOT NULL
);
CREATE TABLE weather.auth_sessions (
    token_hash text PRIMARY KEY,
    csrf_hash text NOT NULL,
    kind text NOT NULL CHECK (kind IN ('challenge', 'session')),
    created_at timestamptz NOT NULL,
    expires_at timestamptz NOT NULL,
    revoked boolean NOT NULL DEFAULT FALSE,
    CHECK (expires_at > created_at AND expires_at <= created_at + INTERVAL '60 days')
);
CREATE INDEX auth_sessions_expiry ON weather.auth_sessions (expires_at);
CREATE TABLE weather.auth_limits (
    scope text PRIMARY KEY CHECK (scope IN ('challenge', 'login-global', 'login-owner')),
    window_start timestamptz NOT NULL,
    attempts integer NOT NULL CHECK (attempts > 0)
);
