"""Import named OSM road segments for Kota Bandung, Kota Cimahi, and Kabupaten Bandung."""

from __future__ import annotations

import argparse
import json
import re
import time
from collections import Counter
from pathlib import Path

import requests
from psycopg.types.json import Jsonb

from api.db import get_connection
from scripts.migrate_csv_to_postgres import apply_schema


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BOUNDARIES_PATH = PROJECT_ROOT / "data" / "boundaries.geojson"
REGIONS = {
    "kota-bandung": {
        "name": "Kota Bandung",
        "area_type": "city",
        "relation_id": 13290062,
        "boundary_name": "Bandung City",
        "tile_size": 0.035,
    },
    "kota-cimahi": {
        "name": "Kota Cimahi",
        "area_type": "city",
        "relation_id": 14935961,
        "boundary_name": "Cimahi",
        "tile_size": 0.035,
    },
    "kabupaten-bandung": {
        "name": "Kabupaten Bandung",
        "area_type": "regency",
        "relation_id": 14935959,
        "boundary_name": "Kabupaten Bandung",
        "tile_size": 0.1,
    },
}
OVERPASS_ENDPOINTS = [
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
    "https://overpass-api.de/api/interpreter",
]
NON_REPORTABLE_HIGHWAYS = {"bridleway", "cycleway", "footway", "path", "pedestrian", "steps"}


def _normalize_name(value):
    normalized = re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()
    return re.sub(r"^(?:jalan|jl)\s+", "", normalized).strip()


def _line_wkt(geometry):
    points = []
    for point in geometry or []:
        if "lon" in point and "lat" in point:
            points.append((float(point["lon"]), float(point["lat"])))
    if len(points) < 2:
        return None
    return "LINESTRING(" + ", ".join(f"{longitude} {latitude}" for longitude, latitude in points) + ")"


def _load_boundary_features():
    features = json.loads(BOUNDARIES_PATH.read_text(encoding="utf-8"))["features"]
    features_by_relation_id = {}
    for feature in features:
        relation_id = feature.get("properties", {}).get("osm_id")
        if relation_id is not None:
            features_by_relation_id[int(relation_id)] = feature
    return features_by_relation_id


def _region_bbox(feature):
    properties = feature.get("properties", {})
    return (
        float(properties["bbox_west"]),
        float(properties["bbox_south"]),
        float(properties["bbox_east"]),
        float(properties["bbox_north"]),
    )


def _tiles_for_region(feature, tile_size):
    west, south, east, north = _region_bbox(feature)
    longitude = west
    while longitude < east:
        latitude = south
        tile_east = min(longitude + tile_size, east)
        while latitude < north:
            tile_north = min(latitude + tile_size, north)
            yield (longitude, latitude, tile_east, tile_north)
            latitude = tile_north
        longitude = tile_east


def _upsert_administrative_areas(connection):
    features = _load_boundary_features()
    query = """
        INSERT INTO administrative_areas (slug, name, area_type, osm_relation_id, boundary, updated_at)
        VALUES (%s, %s, %s, %s, ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326), NOW())
        ON CONFLICT (slug) DO UPDATE SET
            name = EXCLUDED.name,
            area_type = EXCLUDED.area_type,
            osm_relation_id = EXCLUDED.osm_relation_id,
            boundary = EXCLUDED.boundary,
            updated_at = NOW()
        RETURNING id
    """
    area_ids = {}
    with connection.cursor() as cursor:
        for slug, region in REGIONS.items():
            feature = features.get(region["relation_id"])
            if feature is None:
                raise RuntimeError(f"Batas OSM untuk {region['name']} tidak ditemukan dalam {BOUNDARIES_PATH.name}.")
            cursor.execute(
                query,
                (
                    slug,
                    region["name"],
                    region["area_type"],
                    region["relation_id"],
                    json.dumps(feature["geometry"]),
                ),
            )
            area_ids[slug] = cursor.fetchone()["id"]
    return area_ids, features


def _build_overpass_query(bounds):
    west, south, east, north = bounds
    return f"""
        [out:json][timeout:120][maxsize:268435456];
        way[highway][name]({south},{west},{north},{east});
        out tags geom;
    """


def _fetch_ways(region, bounds, endpoints, timeout):
    query = _build_overpass_query(bounds)
    errors = []
    for endpoint in endpoints:
        try:
            response = requests.post(
                endpoint,
                data={"data": query},
                headers={"User-Agent": "bandung-crime-dashboard/0.1 (road-import)"},
                timeout=timeout,
            )
            if response.status_code in {429, 504}:
                errors.append(f"{endpoint}: HTTP {response.status_code}")
                continue
            response.raise_for_status()
            payload = response.json()
            return payload.get("elements", []), endpoint
        except (requests.RequestException, ValueError) as error:
            errors.append(f"{endpoint}: {error}")
    raise RuntimeError(f"Tidak dapat mengambil ruas untuk {region['name']}. {' | '.join(errors)}")


def _upsert_roads(connection, area_id, ways):
    road_query = """
        INSERT INTO road_segments (
            osm_way_id, name, search_name, highway_type, osm_tags,
            road_geometry, road_center, is_reportable, source_updated_at
        ) VALUES (
            %(osm_way_id)s, %(name)s, %(search_name)s, %(highway_type)s, %(osm_tags)s,
            ST_GeomFromText(%(road_wkt)s, 4326),
            ST_PointOnSurface(ST_GeomFromText(%(road_wkt)s, 4326)),
            %(is_reportable)s, NOW()
        )
        ON CONFLICT (osm_way_id) DO UPDATE SET
            name = EXCLUDED.name,
            search_name = EXCLUDED.search_name,
            highway_type = EXCLUDED.highway_type,
            osm_tags = EXCLUDED.osm_tags,
            road_geometry = EXCLUDED.road_geometry,
            road_center = EXCLUDED.road_center,
            is_reportable = EXCLUDED.is_reportable,
            source_updated_at = NOW()
    """
    membership_query = """
        INSERT INTO road_area_memberships (road_way_id, administrative_area_id)
        SELECT road.osm_way_id, area.id
        FROM road_segments AS road
        INNER JOIN administrative_areas AS area ON area.id = %s
        WHERE road.osm_way_id = %s
          AND ST_Intersects(road.road_geometry, area.boundary)
        ON CONFLICT DO NOTHING
    """
    summary = Counter()
    with connection.cursor() as cursor:
        for way in ways:
            tags = way.get("tags", {})
            name = str(tags.get("name", "")).strip()
            highway_type = str(tags.get("highway", "")).strip()
            road_wkt = _line_wkt(way.get("geometry"))
            if not name or not highway_type or not road_wkt:
                summary["skipped"] += 1
                continue
            cursor.execute(
                road_query,
                {
                    "osm_way_id": int(way["id"]),
                    "name": name,
                    "search_name": _normalize_name(name),
                    "highway_type": highway_type,
                    "osm_tags": Jsonb(tags),
                    "road_wkt": road_wkt,
                    "is_reportable": highway_type not in NON_REPORTABLE_HIGHWAYS,
                },
            )
            cursor.execute(membership_query, (area_id, int(way["id"])))
            summary["imported"] += 1
    return summary


def _delete_unassociated_roads(connection):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            DELETE FROM road_segments AS road
            WHERE NOT EXISTS (
                SELECT 1
                FROM road_area_memberships AS membership
                WHERE membership.road_way_id = road.osm_way_id
            )
            """
        )
        return cursor.rowcount


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--region", action="append", choices=sorted(REGIONS), help="Batasi impor ke satu atau lebih wilayah.")
    parser.add_argument("--overpass-url", action="append", dest="overpass_urls", help="Endpoint Overpass tambahan atau pengganti.")
    parser.add_argument("--timeout", type=int, default=120, help="Batas waktu request per endpoint dalam detik.")
    parser.add_argument("--cleanup-only", action="store_true", help="Hapus segmen yang tidak beririsan dengan tiga wilayah target.")
    args = parser.parse_args()

    selected_slugs = args.region or list(REGIONS)
    endpoints = args.overpass_urls or OVERPASS_ENDPOINTS
    with get_connection() as connection:
        apply_schema(connection)
        area_ids, features = _upsert_administrative_areas(connection)
        connection.commit()

        if args.cleanup_only:
            removed = _delete_unassociated_roads(connection)
            connection.commit()
            print(f"Removed {removed} road segments outside the three target areas.")
            return

        overall = Counter()
        for slug in selected_slugs:
            region = REGIONS[slug]
            feature = features[region["relation_id"]]
            tiles = list(_tiles_for_region(feature, region["tile_size"]))
            region_summary = Counter()
            print(f"Fetching {region['name']} in {len(tiles)} tiles...", flush=True)
            for tile_number, bounds in enumerate(tiles, start=1):
                ways, endpoint = _fetch_ways(region, bounds, endpoints, args.timeout)
                summary = _upsert_roads(connection, area_ids[slug], ways)
                connection.commit()
                region_summary.update(summary)
                print(
                    f"  Tile {tile_number}/{len(tiles)}: {len(ways)} ways from {endpoint} "
                    f"(upserted: {summary['imported']}, skipped: {summary['skipped']})",
                    flush=True,
                )
                time.sleep(1)
            overall.update(region_summary)
            print(f"  {region['name']} complete: {dict(region_summary)}", flush=True)

        removed = _delete_unassociated_roads(connection)
        connection.commit()
    print("Road import completed:", dict(overall))
    print(f"Removed outside-area segments: {removed}")


if __name__ == "__main__":
    main()
