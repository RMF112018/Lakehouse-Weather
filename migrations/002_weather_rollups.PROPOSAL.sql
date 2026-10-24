-- Owner-controlled additive follow-on to the frozen seven-table weather schema.
-- Keep all raw observations. No roles, credentials, owner-chain stamping or deletes.
CREATE TABLE weather.observation_rollups (
    station_id text NOT NULL REFERENCES weather.stations(id),
    bucket_start timestamptz NOT NULL,
    bucket_seconds integer NOT NULL CHECK (bucket_seconds IN (300, 3600, 86400)),
    summary jsonb NOT NULL CHECK (jsonb_typeof(summary) = 'object'),
    PRIMARY KEY (station_id, bucket_seconds, bucket_start)
);
