"""Postgres queries shared by the internal Streamlit dashboard."""

from __future__ import annotations

from collections.abc import Iterable

import pandas as pd
from psycopg.types.json import Jsonb

from api.db import get_connection
from api.road_matching import match_road, normalize_road_name


PUBLIC_COLUMNS = [
    "id",
    "timestamp",
    "latitude",
    "longitude",
    "type",
    "description",
    "reporter_name",
    "latitude_original",
    "longitude_original",
    "street_name_raw",
    "street_name_normalized",
    "road_way_id",
    "location_status",
    "location_precision",
    "geocode_source",
    "coordinate_adjustment_m",
    "location_review_reason",
    "is_mappable",
]

MODERATION_STATUSES = ("pending", "published", "needs_review", "rejected")


def _as_dataframe(rows, columns):
    dataframe = pd.DataFrame(rows, columns=columns)
    if "timestamp" in dataframe:
        dataframe["timestamp"] = pd.to_datetime(dataframe["timestamp"], errors="coerce")
    return dataframe


def load_published_incidents():
    """Return only map-safe incidents that moderators have published."""
    query = """
        SELECT
            id,
            occurred_at AS timestamp,
            latitude,
            longitude,
            crime_type AS type,
            description,
            COALESCE(reporter_name, 'Anonim') AS reporter_name,
            latitude_original,
            longitude_original,
            street_name_raw,
            street_name_normalized,
            road_way_id,
            location_status,
            location_precision,
            geocode_source,
            coordinate_adjustment_m,
            location_review_reason,
            is_mappable
        FROM incidents
        WHERE moderation_status = 'published'
          AND is_mappable = TRUE
          AND incident_location IS NOT NULL
        ORDER BY occurred_at DESC, id DESC
    """
    with get_connection() as connection, connection.cursor() as cursor:
        cursor.execute(query)
        rows = cursor.fetchall()
    return _as_dataframe(rows, PUBLIC_COLUMNS)


def search_reportable_roads(query, limit=20):
    """Search selectable OSM road segments within Bandung Raya."""
    normalized_query = normalize_road_name(query)
    if len(normalized_query) < 2:
        return []
    query_sql = """
        SELECT DISTINCT
            road.osm_way_id,
            road.name,
            road.highway_type,
            ST_Y(road.road_center) AS latitude,
            ST_X(road.road_center) AS longitude
        FROM road_segments AS road
        INNER JOIN road_area_memberships AS membership
            ON membership.road_way_id = road.osm_way_id
        WHERE road.is_reportable = TRUE
          AND road.search_name ILIKE %s
        ORDER BY road.name, road.osm_way_id
        LIMIT %s
    """
    with get_connection() as connection, connection.cursor() as cursor:
        cursor.execute(query_sql, (f"%{normalized_query}%", limit))
        return cursor.fetchall()


def preview_location_correction(road_way_id):
    """Return a verified point for an explicitly selected OSM road segment."""
    with get_connection() as connection:
        road_match = match_road(connection, "ruas jalan", road_way_id)
    if road_match.status != "exact":
        raise ValueError("Ruas jalan tidak dapat digunakan untuk koreksi lokasi.")
    return road_match.as_dict()


def get_moderation_counts():
    """Return a complete status count map, including empty statuses."""
    counts = {status: 0 for status in MODERATION_STATUSES}
    with get_connection() as connection, connection.cursor() as cursor:
        cursor.execute(
            "SELECT moderation_status, COUNT(*) AS count FROM incidents GROUP BY moderation_status"
        )
        rows = cursor.fetchall()
    counts.update({row["moderation_status"]: row["count"] for row in rows})
    return counts


def list_moderation_incidents(statuses: Iterable[str], limit=200):
    """List newest reports in moderator-safe detail for the internal queue."""
    selected_statuses = list(dict.fromkeys(statuses))
    if not selected_statuses:
        return []
    unknown_statuses = set(selected_statuses).difference(MODERATION_STATUSES)
    if unknown_statuses:
        raise ValueError(f"Invalid moderation statuses: {sorted(unknown_statuses)}")

    query = """
        SELECT
            id,
            occurred_at,
            crime_type,
            description,
            street_name_raw,
            street_name_normalized,
            road_way_id,
            latitude,
            longitude,
            location_status,
            location_precision,
            geocode_source,
            location_review_reason,
            is_mappable,
            moderation_status,
            moderation_note,
            moderated_at,
            moderated_by,
            source_name,
            created_at
        FROM incidents
        WHERE moderation_status = ANY(%s)
        ORDER BY occurred_at DESC, id DESC
        LIMIT %s
    """
    with get_connection() as connection, connection.cursor() as cursor:
        cursor.execute(query, (selected_statuses, limit))
        return cursor.fetchall()


def update_moderation_status(incident_id, moderation_status, moderator_name, moderation_note=None):
    """Persist a moderator decision and prevent unsafe reports from publishing."""
    if moderation_status not in MODERATION_STATUSES:
        raise ValueError("Status moderasi tidak valid.")
    if moderation_status == "pending":
        raise ValueError("Laporan baru tidak dapat dikembalikan ke status pending.")
    if not moderator_name.strip():
        raise ValueError("Nama moderator wajib tersedia.")

    with get_connection() as connection, connection.cursor() as cursor:
        cursor.execute(
            "SELECT id, is_mappable FROM incidents WHERE id = %s FOR UPDATE",
            (incident_id,),
        )
        incident = cursor.fetchone()
        if incident is None:
            raise ValueError("Laporan tidak ditemukan.")
        if moderation_status == "published" and not incident["is_mappable"]:
            raise ValueError(
                "Laporan ini belum memiliki lokasi yang aman untuk dipublikasikan. "
                "Tandai sebagai perlu ditinjau."
            )

        cursor.execute(
            """
            UPDATE incidents
            SET moderation_status = %s,
                moderation_note = %s,
                moderated_by = %s,
                moderated_at = NOW(),
                updated_at = NOW()
            WHERE id = %s
            RETURNING id, moderation_status, moderated_at
            """,
            (moderation_status, moderation_note or None, moderator_name.strip(), incident_id),
        )
        updated_incident = cursor.fetchone()
        connection.commit()
    return updated_incident


def list_location_revisions(incident_id, limit=10):
    """Return prior corrections without exposing them to the public dashboard."""
    with get_connection() as connection, connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT corrected_at, corrected_by, correction_reason,
                   previous_location, corrected_location
            FROM incident_location_revisions
            WHERE incident_id = %s
            ORDER BY corrected_at DESC
            LIMIT %s
            """,
            (incident_id, limit),
        )
        return cursor.fetchall()


def correct_incident_location(incident_id, road_way_id, correction_reason, moderator_name):
    """Correct an incident to a selected road and preserve an immutable audit record."""
    if len(correction_reason.strip()) < 10:
        raise ValueError("Alasan koreksi lokasi minimal 10 karakter.")
    if not moderator_name.strip():
        raise ValueError("Nama moderator wajib tersedia.")

    with get_connection() as connection, connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT id, street_name_raw, street_name_normalized, road_way_id,
                   latitude, longitude, location_status, location_precision,
                   geocode_source, location_review_reason, is_mappable,
                   moderation_status
            FROM incidents
            WHERE id = %s
            FOR UPDATE
            """,
            (incident_id,),
        )
        incident = cursor.fetchone()
        if incident is None:
            raise ValueError("Laporan tidak ditemukan.")

        road_match = match_road(connection, "ruas jalan", road_way_id)
        if road_match.status != "exact" or road_match.latitude is None or road_match.longitude is None:
            raise ValueError("Ruas jalan tidak dapat digunakan untuk koreksi lokasi.")

        previous_location = {
            "street_name_raw": incident["street_name_raw"],
            "street_name_normalized": incident["street_name_normalized"],
            "road_way_id": incident["road_way_id"],
            "latitude": incident["latitude"],
            "longitude": incident["longitude"],
            "location_status": incident["location_status"],
            "location_precision": incident["location_precision"],
            "geocode_source": incident["geocode_source"],
            "location_review_reason": incident["location_review_reason"],
            "is_mappable": incident["is_mappable"],
            "moderation_status": incident["moderation_status"],
        }
        corrected_location = {
            "street_name_normalized": road_match.street_name_normalized,
            "road_way_id": road_match.road_way_id,
            "latitude": road_match.latitude,
            "longitude": road_match.longitude,
            "location_status": "moderator_corrected",
            "location_precision": road_match.location_precision,
            "geocode_source": "moderator_osm_selected_road",
            "location_review_reason": correction_reason.strip(),
            "is_mappable": True,
            "moderation_status": "needs_review",
        }
        cursor.execute(
            """
            UPDATE incidents
            SET street_name_normalized = %(street_name_normalized)s,
                road_way_id = %(road_way_id)s,
                latitude = %(latitude)s,
                longitude = %(longitude)s,
                incident_location = ST_SetSRID(ST_MakePoint(%(longitude)s, %(latitude)s), 4326),
                location_status = %(location_status)s,
                location_precision = %(location_precision)s,
                geocode_source = %(geocode_source)s,
                location_review_reason = %(location_review_reason)s,
                is_mappable = TRUE,
                moderation_status = 'needs_review',
                updated_at = NOW()
            WHERE id = %(incident_id)s
            RETURNING id, street_name_normalized, road_way_id, moderation_status
            """,
            {**corrected_location, "incident_id": incident_id},
        )
        corrected_incident = cursor.fetchone()
        cursor.execute(
            """
            INSERT INTO incident_location_revisions (
                incident_id, previous_location, corrected_location,
                correction_reason, corrected_by
            ) VALUES (%s, %s, %s, %s, %s)
            """,
            (
                incident_id,
                Jsonb(previous_location),
                Jsonb(corrected_location),
                correction_reason.strip(),
                moderator_name.strip(),
            ),
        )
        connection.commit()
    return corrected_incident
