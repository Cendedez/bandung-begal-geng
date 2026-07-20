"""Road matching with conservative confidence levels for citizen reports."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field


NON_ALPHANUMERIC = re.compile(r"[^a-z0-9]+")
ROAD_PREFIX = re.compile(r"^(?:jalan|jl|jln)\s+")


@dataclass
class RoadCandidate:
    osm_way_id: int
    name: str
    highway_type: str
    latitude: float
    longitude: float
    score: float | None = None


@dataclass
class RoadMatch:
    status: str
    confidence: float
    street_name_normalized: str | None = None
    road_way_id: int | None = None
    latitude: float | None = None
    longitude: float | None = None
    location_precision: str = "unknown"
    geocode_source: str = "road_matcher"
    review_reason: str = ""
    candidates: list[RoadCandidate] = field(default_factory=list)

    def as_dict(self):
        payload = asdict(self)
        payload["candidates"] = [asdict(candidate) for candidate in self.candidates]
        return payload


def normalize_road_name(value):
    normalized = NON_ALPHANUMERIC.sub(" ", str(value).lower()).strip()
    return ROAD_PREFIX.sub("", normalized).strip()


def _row_to_candidate(row, score=None):
    return RoadCandidate(
        osm_way_id=int(row["osm_way_id"]),
        name=row["name"],
        highway_type=row["highway_type"],
        latitude=float(row["latitude"]),
        longitude=float(row["longitude"]),
        score=round(float(score), 3) if score is not None else None,
    )


def _find_selected_road(connection, road_way_id):
    query = """
        SELECT DISTINCT
            road.osm_way_id,
            road.name,
            road.highway_type,
            ST_Y(road.road_center) AS latitude,
            ST_X(road.road_center) AS longitude
        FROM road_segments AS road
        INNER JOIN road_area_memberships AS membership
            ON membership.road_way_id = road.osm_way_id
        WHERE road.osm_way_id = %s
          AND road.is_reportable = TRUE
    """
    with connection.cursor() as cursor:
        cursor.execute(query, (road_way_id,))
        return cursor.fetchone()


def _find_audited_alias(connection, normalized_name):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT canonical_name, aliases, mappable, reference_latitude, reference_longitude, reason
            FROM street_references
            """
        )
        references = cursor.fetchall()

    for reference in references:
        names = [reference["canonical_name"], *(reference["aliases"] or [])]
        if any(normalize_road_name(name) == normalized_name for name in names):
            return reference
    return None


def _find_exact_road(connection, normalized_name):
    query = """
        SELECT
            road.search_name,
            MIN(road.osm_way_id) AS osm_way_id,
            MIN(road.name) AS name,
            MIN(road.highway_type) AS highway_type,
            COUNT(DISTINCT membership.administrative_area_id) AS area_count,
            ST_Y(ST_PointOnSurface(ST_Collect(road.road_geometry))) AS latitude,
            ST_X(ST_PointOnSurface(ST_Collect(road.road_geometry))) AS longitude
        FROM road_segments AS road
        INNER JOIN road_area_memberships AS membership
            ON membership.road_way_id = road.osm_way_id
        WHERE road.is_reportable = TRUE
          AND road.search_name = %s
        GROUP BY road.search_name
    """
    with connection.cursor() as cursor:
        cursor.execute(query, (normalized_name,))
        return cursor.fetchone()


def _find_fuzzy_candidates(connection, normalized_name):
    query = """
        WITH candidates AS (
            SELECT
                road.search_name,
                MIN(road.osm_way_id) AS osm_way_id,
                MIN(road.name) AS name,
                MIN(road.highway_type) AS highway_type,
                MAX(similarity(road.search_name, %s)) AS score,
                ST_Y(ST_PointOnSurface(ST_Collect(road.road_geometry))) AS latitude,
                ST_X(ST_PointOnSurface(ST_Collect(road.road_geometry))) AS longitude
            FROM road_segments AS road
            INNER JOIN road_area_memberships AS membership
                ON membership.road_way_id = road.osm_way_id
            WHERE road.is_reportable = TRUE
              AND similarity(road.search_name, %s) >= 0.42
            GROUP BY road.search_name
        )
        SELECT *
        FROM candidates
        ORDER BY score DESC, name
        LIMIT 5
    """
    with connection.cursor() as cursor:
        cursor.execute(query, (normalized_name, normalized_name))
        rows = cursor.fetchall()
    return [_row_to_candidate(row, row["score"]) for row in rows]


def match_road(connection, road_name, road_way_id=None):
    """Match a report road conservatively; fuzzy matches never receive a coordinate."""
    normalized_name = normalize_road_name(road_name)
    if not normalized_name:
        return RoadMatch(status="needs_review", confidence=0, review_reason="Nama jalan belum diisi.")

    if road_way_id is not None:
        selected_road = _find_selected_road(connection, road_way_id)
        if selected_road is None:
            return RoadMatch(
                status="needs_review",
                confidence=0,
                review_reason="Ruas jalan yang dipilih tidak berada di tiga wilayah Bandung Raya.",
            )
        candidate = _row_to_candidate(selected_road)
        return RoadMatch(
            status="exact",
            confidence=1,
            street_name_normalized=candidate.name,
            road_way_id=candidate.osm_way_id,
            latitude=candidate.latitude,
            longitude=candidate.longitude,
            location_precision="road_segment",
            geocode_source="osm_selected_road",
            review_reason="Ruas jalan dipilih langsung dari master OSM Bandung Raya.",
        )

    audited_reference = _find_audited_alias(connection, normalized_name)
    if audited_reference is not None:
        if not audited_reference["mappable"]:
            return RoadMatch(
                status="needs_review",
                confidence=0.6,
                street_name_normalized=audited_reference["canonical_name"],
                review_reason=audited_reference["reason"] or "Nama lokasi perlu diperjelas.",
            )
        return RoadMatch(
            status="alias_match",
            confidence=0.92,
            street_name_normalized=audited_reference["canonical_name"],
            latitude=float(audited_reference["reference_latitude"]),
            longitude=float(audited_reference["reference_longitude"]),
            location_precision="road_reference",
            geocode_source="audited_street_reference",
            review_reason="Nama jalan cocok dengan alias pada katalog referensi yang diaudit.",
        )

    exact_road = _find_exact_road(connection, normalized_name)
    if exact_road is not None:
        candidate = _row_to_candidate(exact_road)
        if int(exact_road["area_count"]) == 1:
            return RoadMatch(
                status="exact",
                confidence=0.9,
                street_name_normalized=candidate.name,
                road_way_id=candidate.osm_way_id,
                latitude=candidate.latitude,
                longitude=candidate.longitude,
                location_precision="road_name",
                geocode_source="osm_exact_name",
                review_reason="Nama ruas cocok tepat pada satu wilayah administratif.",
            )
        return RoadMatch(
            status="ambiguous",
            confidence=0.55,
            street_name_normalized=candidate.name,
            review_reason="Nama jalan yang sama muncul di lebih dari satu wilayah; pilih hasil pencarian jalan.",
            candidates=[candidate],
        )

    candidates = _find_fuzzy_candidates(connection, normalized_name)
    if candidates:
        return RoadMatch(
            status="ambiguous",
            confidence=candidates[0].score or 0,
            review_reason="Nama jalan mendekati beberapa ruas; pilih satu ruas agar lokasi dapat diverifikasi.",
            candidates=candidates,
        )
    return RoadMatch(
        status="needs_review",
        confidence=0,
        review_reason="Nama jalan tidak ditemukan dalam master Bandung Raya.",
    )
