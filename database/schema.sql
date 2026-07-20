CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE TABLE IF NOT EXISTS street_references (
    canonical_name TEXT PRIMARY KEY,
    aliases JSONB NOT NULL DEFAULT '[]'::jsonb,
    road_names JSONB NOT NULL DEFAULT '[]'::jsonb,
    osm_way_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    mappable BOOLEAN NOT NULL,
    reference_latitude DOUBLE PRECISION,
    reference_longitude DOUBLE PRECISION,
    reference_location geometry(Point, 4326),
    reason TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (
        (mappable AND reference_latitude IS NOT NULL AND reference_longitude IS NOT NULL)
        OR NOT mappable
    )
);

CREATE INDEX IF NOT EXISTS street_references_location_gix
    ON street_references USING GIST (reference_location);

CREATE TABLE IF NOT EXISTS incidents (
    id BIGSERIAL PRIMARY KEY,
    legacy_id BIGINT UNIQUE,
    occurred_at TIMESTAMPTZ NOT NULL,
    crime_type TEXT NOT NULL CHECK (crime_type IN ('Begal', 'Geng Motor')),
    description TEXT NOT NULL,
    reporter_name TEXT,
    street_name_raw TEXT,
    street_name_normalized TEXT,
    road_way_id BIGINT,
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    latitude_original DOUBLE PRECISION,
    longitude_original DOUBLE PRECISION,
    incident_location geometry(Point, 4326),
    location_status TEXT NOT NULL,
    location_precision TEXT NOT NULL,
    geocode_source TEXT,
    coordinate_adjustment_m DOUBLE PRECISION,
    location_review_reason TEXT,
    is_mappable BOOLEAN NOT NULL DEFAULT FALSE,
    moderation_status TEXT NOT NULL DEFAULT 'pending'
        CHECK (moderation_status IN ('pending', 'published', 'needs_review', 'rejected')),
    moderation_note TEXT,
    moderated_at TIMESTAMPTZ,
    moderated_by TEXT,
    source_name TEXT NOT NULL DEFAULT 'citizen_report',
    report_fingerprint TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (
        (is_mappable AND latitude IS NOT NULL AND longitude IS NOT NULL AND incident_location IS NOT NULL)
        OR NOT is_mappable
    )
);

CREATE INDEX IF NOT EXISTS incidents_public_map_idx
    ON incidents (moderation_status, crime_type, occurred_at DESC)
    WHERE is_mappable;

CREATE INDEX IF NOT EXISTS incidents_location_gix
    ON incidents USING GIST (incident_location)
    WHERE is_mappable;

CREATE INDEX IF NOT EXISTS incidents_street_name_idx
    ON incidents (street_name_normalized);

ALTER TABLE incidents
    ADD COLUMN IF NOT EXISTS report_fingerprint TEXT;

ALTER TABLE incidents
    ADD COLUMN IF NOT EXISTS moderation_note TEXT;

ALTER TABLE incidents
    ADD COLUMN IF NOT EXISTS moderated_at TIMESTAMPTZ;

ALTER TABLE incidents
    ADD COLUMN IF NOT EXISTS moderated_by TEXT;

ALTER TABLE incidents
    ADD COLUMN IF NOT EXISTS road_way_id BIGINT;

CREATE UNIQUE INDEX IF NOT EXISTS incidents_report_fingerprint_unique_idx
    ON incidents (report_fingerprint)
    WHERE report_fingerprint IS NOT NULL;

CREATE TABLE IF NOT EXISTS administrative_areas (
    id SMALLSERIAL PRIMARY KEY,
    slug TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL UNIQUE,
    area_type TEXT NOT NULL CHECK (area_type IN ('city', 'regency')),
    osm_relation_id BIGINT NOT NULL UNIQUE,
    boundary geometry(Geometry, 4326) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS administrative_areas_boundary_gix
    ON administrative_areas USING GIST (boundary);

CREATE TABLE IF NOT EXISTS road_segments (
    osm_way_id BIGINT PRIMARY KEY,
    name TEXT NOT NULL,
    search_name TEXT NOT NULL,
    highway_type TEXT NOT NULL,
    osm_tags JSONB NOT NULL DEFAULT '{}'::jsonb,
    road_geometry geometry(LineString, 4326) NOT NULL,
    road_center geometry(Point, 4326) NOT NULL,
    is_reportable BOOLEAN NOT NULL DEFAULT TRUE,
    source_updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS road_segments_geometry_gix
    ON road_segments USING GIST (road_geometry);

CREATE INDEX IF NOT EXISTS road_segments_search_trgm_idx
    ON road_segments USING GIN (search_name gin_trgm_ops);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'incidents_road_way_id_fkey'
    ) THEN
        ALTER TABLE incidents
            ADD CONSTRAINT incidents_road_way_id_fkey
            FOREIGN KEY (road_way_id)
            REFERENCES road_segments(osm_way_id);
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS incident_location_revisions (
    id BIGSERIAL PRIMARY KEY,
    incident_id BIGINT NOT NULL REFERENCES incidents(id) ON DELETE CASCADE,
    previous_location JSONB NOT NULL,
    corrected_location JSONB NOT NULL,
    correction_reason TEXT NOT NULL,
    corrected_by TEXT NOT NULL,
    corrected_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS incident_location_revisions_incident_idx
    ON incident_location_revisions (incident_id, corrected_at DESC);

CREATE TABLE IF NOT EXISTS road_area_memberships (
    road_way_id BIGINT NOT NULL REFERENCES road_segments(osm_way_id) ON DELETE CASCADE,
    administrative_area_id SMALLINT NOT NULL REFERENCES administrative_areas(id) ON DELETE CASCADE,
    PRIMARY KEY (road_way_id, administrative_area_id)
);

CREATE INDEX IF NOT EXISTS road_area_memberships_area_idx
    ON road_area_memberships (administrative_area_id, road_way_id);
