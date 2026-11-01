CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE IF NOT EXISTS vessel_positions (
    id BIGSERIAL PRIMARY KEY,
    mmsi BIGINT NOT NULL,
    observed_at TIMESTAMPTZ NOT NULL,
    sog REAL,
    cog REAL,
    source TEXT NOT NULL,
    geom geometry(Point, 4326) NOT NULL
);

CREATE INDEX IF NOT EXISTS vessel_positions_geom_idx ON vessel_positions USING GIST (geom);
CREATE INDEX IF NOT EXISTS vessel_positions_mmsi_time_idx ON vessel_positions (mmsi, observed_at DESC);
