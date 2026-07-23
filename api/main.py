"""FastAPI endpoints for public, location-safe incident data."""

from __future__ import annotations

import hashlib
import re
import time
from collections import defaultdict, deque
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi import FastAPI, HTTPException, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware

from api.config import get_cors_origin_regex, get_cors_origins
from api.db import get_connection
from api.road_matching import match_road, normalize_road_name
from api.schemas import (
    FeatureCollection,
    IncidentDetail,
    ReportSubmission,
    ReportSubmissionResponse,
    RoadMatchRequest,
    RoadMatchResponse,
    RoadSearchResult,
    StreetReference,
)


app = FastAPI(
    title="Bandung Raya Street Crime API",
    version="0.1.0",
    description="Public map data contains only published, map-safe incident locations.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_origins(),
    allow_origin_regex=get_cors_origin_regex(),
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


JAKARTA_TIMEZONE = ZoneInfo("Asia/Jakarta")
REPORT_RATE_LIMIT = 5
REPORT_RATE_WINDOW_SECONDS = 15 * 60
REPORT_ATTEMPTS = defaultdict(deque)
EMAIL_PATTERN = re.compile(r"\b[^\s@]+@[^\s@]+\.[^\s@]+\b", re.IGNORECASE)
PHONE_PATTERN = re.compile(r"(?<!\d)(?:\+?62|0)8[\d\s-]{7,13}(?!\d)")


def _public_filters(start_date, end_date, crime_types, west, south, east, north):
    clauses = [
        "moderation_status = 'published'",
        "is_mappable = TRUE",
        "incident_location IS NOT NULL",
    ]
    parameters = []

    if start_date:
        clauses.append("occurred_at >= %s::date")
        parameters.append(start_date)
    if end_date:
        clauses.append("occurred_at < (%s::date + INTERVAL '1 day')")
        parameters.append(end_date)
    if crime_types:
        clauses.append("crime_type = ANY(%s)")
        parameters.append(crime_types)
    bounds = [west, south, east, north]
    if any(value is not None for value in bounds):
        if any(value is None for value in bounds):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="west, south, east, and north must be supplied together.",
            )
        if west >= east or south >= north:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Bounding box is invalid.",
            )
        clauses.append("incident_location && ST_MakeEnvelope(%s, %s, %s, %s, 4326)")
        parameters.extend(bounds)

    return " AND ".join(clauses), parameters


def _enforce_report_rate_limit(request):
    client_address = request.client.host if request.client else "unknown"
    now = time.monotonic()
    attempts = REPORT_ATTEMPTS[client_address]
    while attempts and now - attempts[0] >= REPORT_RATE_WINDOW_SECONDS:
        attempts.popleft()
    if len(attempts) >= REPORT_RATE_LIMIT:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Terlalu banyak laporan dari perangkat ini. Coba lagi beberapa menit lagi.",
        )
    attempts.append(now)


def _validate_report_description(description):
    if EMAIL_PATTERN.search(description) or PHONE_PATTERN.search(description):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Hapus nomor telepon atau alamat email dari keterangan laporan.",
        )


def _normalize_occurrence_time(occurred_at):
    localized = occurred_at.replace(tzinfo=JAKARTA_TIMEZONE) if occurred_at.tzinfo is None else occurred_at
    if localized.astimezone(timezone.utc) > datetime.now(timezone.utc) + timedelta(minutes=5):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Waktu kejadian tidak boleh berada di masa depan.",
        )
    return localized


def _report_fingerprint(payload, occurred_at, road_match):
    normalized_description = " ".join(payload.description.lower().split())
    road_key = str(road_match.road_way_id or normalize_road_name(payload.road_name))
    time_key = occurred_at.astimezone(JAKARTA_TIMEZONE).replace(second=0, microsecond=0).isoformat()
    source = "|".join((payload.crime_type, road_key, time_key, normalized_description))
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


def _location_payload(road_match):
    mappable = road_match.status in {"exact", "alias_match"} and road_match.latitude is not None and road_match.longitude is not None
    status_by_match = {
        "exact": "pending_road_exact",
        "alias_match": "pending_alias_match",
        "ambiguous": "pending_road_ambiguous",
        "needs_review": "pending_needs_review",
    }
    return {
        "road_way_id": road_match.road_way_id,
        "latitude": road_match.latitude if mappable else None,
        "longitude": road_match.longitude if mappable else None,
        "street_name_normalized": road_match.street_name_normalized,
        "location_status": status_by_match[road_match.status],
        "location_precision": road_match.location_precision if mappable else "unknown",
        "geocode_source": road_match.geocode_source,
        "location_review_reason": road_match.review_reason,
        "is_mappable": mappable,
    }


@app.get("/health")
def health_check():
    try:
        with get_connection() as connection, connection.cursor() as cursor:
            cursor.execute("SELECT PostGIS_Version() AS postgis_version")
            row = cursor.fetchone()
    except Exception as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable.") from error
    return {"status": "ok", "database": "ok", "postgis_version": row["postgis_version"]}


@app.get("/debug/headers")
def debug_headers(request: Request):
    return dict(request.headers)


@app.get("/v1/incidents", response_model=FeatureCollection)
def list_incidents(
    start_date: date | None = None,
    end_date: date | None = None,
    crime_type: list[str] | None = Query(default=None),
    west: float | None = None,
    south: float | None = None,
    east: float | None = None,
    north: float | None = None,
    limit: int = Query(default=1_000, ge=1, le=5_000),
):
    if start_date and end_date and start_date > end_date:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="start_date must not exceed end_date.")
    if crime_type and not set(crime_type).issubset({"Begal", "Geng Motor"}):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="crime_type is invalid.")

    where_clause, parameters = _public_filters(start_date, end_date, crime_type, west, south, east, north)
    query = f"""
        SELECT
            id,
            occurred_at,
            crime_type,
            street_name_normalized,
            location_precision,
            ST_X(incident_location) AS longitude,
            ST_Y(incident_location) AS latitude,
            COUNT(*) OVER() AS total
        FROM incidents
        WHERE {where_clause}
        ORDER BY occurred_at DESC, id DESC
        LIMIT %s
    """
    with get_connection() as connection, connection.cursor() as cursor:
        cursor.execute(query, [*parameters, limit])
        rows = cursor.fetchall()

    total = rows[0]["total"] if rows else 0
    features = [
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [row["longitude"], row["latitude"]]},
            "properties": {
                "id": row["id"],
                "occurred_at": row["occurred_at"],
                "crime_type": row["crime_type"],
                "street_name": row["street_name_normalized"],
                "location_precision": row["location_precision"],
            },
        }
        for row in rows
    ]
    return {"type": "FeatureCollection", "features": features, "total": total}


@app.get("/v1/incidents/{incident_id}", response_model=IncidentDetail)
def get_incident(incident_id: int):
    query = """
        SELECT id, occurred_at, crime_type, description, street_name_normalized,
               location_precision, location_status, location_review_reason
        FROM incidents
        WHERE id = %s
          AND moderation_status = 'published'
          AND is_mappable = TRUE
    """
    with get_connection() as connection, connection.cursor() as cursor:
        cursor.execute(query, (incident_id,))
        row = cursor.fetchone()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found.")
    return {
        "id": row["id"],
        "occurred_at": row["occurred_at"],
        "crime_type": row["crime_type"],
        "street_name": row["street_name_normalized"],
        "location_precision": row["location_precision"],
        "description": row["description"],
        "location_status": row["location_status"],
        "location_review_reason": row["location_review_reason"],
    }


@app.get("/v1/streets", response_model=list[StreetReference])
def list_reportable_streets():
    with get_connection() as connection, connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT canonical_name, reference_latitude, reference_longitude
            FROM street_references
            WHERE mappable = TRUE
            ORDER BY canonical_name
            """
        )
        rows = cursor.fetchall()
    return [
        {"name": row["canonical_name"], "latitude": row["reference_latitude"], "longitude": row["reference_longitude"]}
        for row in rows
    ]


@app.get("/v1/roads/search", response_model=list[RoadSearchResult])
def search_roads(
    q: str = Query(min_length=2, max_length=120),
    limit: int = Query(default=20, ge=1, le=50),
):
    normalized_query = " ".join(q.lower().split())
    query = """
        SELECT DISTINCT ON (search_name)
            r.osm_way_id,
            r.name,
            r.highway_type,
            ST_Y(r.road_center) AS latitude,
            ST_X(r.road_center) AS longitude
        FROM road_segments AS r
        INNER JOIN road_area_memberships AS membership
            ON membership.road_way_id = r.osm_way_id
        WHERE r.is_reportable = TRUE
          AND search_name ILIKE %s
        ORDER BY search_name, r.osm_way_id
        LIMIT %s
    """
    with get_connection() as connection, connection.cursor() as cursor:
        cursor.execute(query, (f"%{normalized_query}%", limit))
        rows = cursor.fetchall()
    return [
        {
            "osm_way_id": row["osm_way_id"],
            "name": row["name"],
            "highway_type": row["highway_type"],
            "latitude": row["latitude"],
            "longitude": row["longitude"],
        }
        for row in rows
    ]


@app.post("/v1/road-match", response_model=RoadMatchResponse)
def preview_road_match(payload: RoadMatchRequest):
    with get_connection() as connection:
        result = match_road(connection, payload.road_name, payload.road_way_id)
    return result.as_dict()


@app.post("/v1/reports", response_model=ReportSubmissionResponse, status_code=status.HTTP_201_CREATED)
def submit_report(payload: ReportSubmission, request: Request):
    _enforce_report_rate_limit(request)
    _validate_report_description(payload.description)
    occurred_at = _normalize_occurrence_time(payload.occurred_at)

    with get_connection() as connection:
        if payload.latitude is not None and payload.longitude is not None:
            from api.road_matching import match_road_by_coordinates
            road_match = match_road_by_coordinates(connection, payload.latitude, payload.longitude)
        else:
            road_match = match_road(connection, payload.road_name, payload.road_way_id)
            
        location = _location_payload(road_match)
        fingerprint = _report_fingerprint(payload, occurred_at, road_match)
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO incidents (
                    occurred_at, crime_type, description, reporter_name,
                    street_name_raw, street_name_normalized,
                    road_way_id,
                    latitude, longitude, incident_location,
                    location_status, location_precision, geocode_source,
                    location_review_reason, is_mappable, moderation_status,
                    source_name, report_fingerprint
                ) VALUES (
                    %(occurred_at)s, %(crime_type)s, %(description)s, %(reporter_name)s,
                    %(street_name_raw)s, %(street_name_normalized)s,
                    %(road_way_id)s,
                    %(latitude)s, %(longitude)s,
                    CASE WHEN %(is_mappable)s THEN ST_SetSRID(ST_MakePoint(%(longitude)s, %(latitude)s), 4326) END,
                    %(location_status)s, %(location_precision)s, %(geocode_source)s,
                    %(location_review_reason)s, %(is_mappable)s, 'pending',
                    'citizen_report', %(report_fingerprint)s
                )
                ON CONFLICT DO NOTHING
                RETURNING id
                """,
                {
                    "occurred_at": occurred_at,
                    "crime_type": payload.crime_type,
                    "description": payload.description,
                    "reporter_name": payload.reporter_name,
                    "street_name_raw": payload.road_name,
                    "street_name_normalized": location["street_name_normalized"],
                    "road_way_id": location["road_way_id"],
                    "latitude": location["latitude"],
                    "longitude": location["longitude"],
                    "location_status": location["location_status"],
                    "location_precision": location["location_precision"],
                    "geocode_source": location["geocode_source"],
                    "location_review_reason": location["location_review_reason"],
                    "is_mappable": location["is_mappable"],
                    "report_fingerprint": fingerprint,
                },
            )
            row = cursor.fetchone()
            if row is None:
                cursor.execute("SELECT id FROM incidents WHERE report_fingerprint = %s", (fingerprint,))
                duplicate = cursor.fetchone()
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={"message": "Laporan serupa sudah diterima dan sedang ditinjau.", "report_id": duplicate["id"] if duplicate else None},
                )
        connection.commit()

    return {"id": row["id"], "moderation_status": "pending", "road_match": road_match.as_dict()}
