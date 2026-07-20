"""Create the PostGIS schema and import audited legacy CSV data safely."""

from __future__ import annotations

import argparse
import json
import shutil
from collections import Counter
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
from psycopg.types.json import Jsonb

from api.db import get_connection


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = PROJECT_ROOT / "database" / "schema.sql"
REFERENCE_PATH = PROJECT_ROOT / "data" / "street_reference.json"
JAKARTA_TIMEZONE = ZoneInfo("Asia/Jakarta")


def _clean_value(value):
    return None if pd.isna(value) else value


def _as_bool(value):
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"true", "1", "yes"}


def _as_timestamp(value):
    parsed = pd.to_datetime(value, errors="raise")
    timestamp = parsed.to_pydatetime()
    return timestamp.replace(tzinfo=JAKARTA_TIMEZONE) if timestamp.tzinfo is None else timestamp


def _moderation_status(location_status, is_mappable):
    if is_mappable:
        return "published"
    if location_status == "out_of_scope":
        return "rejected"
    return "needs_review"


def apply_schema(connection):
    with connection.cursor() as cursor:
        cursor.execute(SCHEMA_PATH.read_text(encoding="utf-8"))


def import_street_references(connection):
    references = json.loads(REFERENCE_PATH.read_text(encoding="utf-8"))["streets"]
    query = """
        INSERT INTO street_references (
            canonical_name, aliases, road_names, osm_way_ids, mappable,
            reference_latitude, reference_longitude, reference_location, reason
        ) VALUES (
            %(canonical_name)s, %(aliases)s, %(road_names)s, %(osm_way_ids)s, %(mappable)s,
            %(latitude)s, %(longitude)s,
            CASE WHEN %(mappable)s THEN ST_SetSRID(ST_MakePoint(%(longitude)s, %(latitude)s), 4326) END,
            %(reason)s
        )
        ON CONFLICT (canonical_name) DO UPDATE SET
            aliases = EXCLUDED.aliases,
            road_names = EXCLUDED.road_names,
            osm_way_ids = EXCLUDED.osm_way_ids,
            mappable = EXCLUDED.mappable,
            reference_latitude = EXCLUDED.reference_latitude,
            reference_longitude = EXCLUDED.reference_longitude,
            reference_location = EXCLUDED.reference_location,
            reason = EXCLUDED.reason,
            updated_at = NOW()
    """
    with connection.cursor() as cursor:
        for reference in references:
            cursor.execute(
                query,
                {
                    "canonical_name": reference["canonical_name"],
                    "aliases": Jsonb(reference.get("aliases", [])),
                    "road_names": Jsonb(reference.get("road_names", [])),
                    "osm_way_ids": Jsonb(reference.get("osm_way_ids", [])),
                    "mappable": reference.get("mappable", False),
                    "latitude": reference.get("latitude"),
                    "longitude": reference.get("longitude"),
                    "reason": reference.get("reason"),
                },
            )
    return len(references)


def import_incidents(connection, csv_path):
    dataframe = pd.read_csv(csv_path)
    summary = Counter()
    query = """
        INSERT INTO incidents (
            legacy_id, occurred_at, crime_type, description, reporter_name,
            street_name_raw, street_name_normalized, latitude, longitude,
            latitude_original, longitude_original, incident_location,
            location_status, location_precision, geocode_source,
            coordinate_adjustment_m, location_review_reason, is_mappable,
            moderation_status, source_name, updated_at
        ) VALUES (
            %(legacy_id)s, %(occurred_at)s, %(crime_type)s, %(description)s, %(reporter_name)s,
            %(street_name_raw)s, %(street_name_normalized)s, %(latitude)s, %(longitude)s,
            %(latitude_original)s, %(longitude_original)s,
            CASE WHEN %(is_mappable)s THEN ST_SetSRID(ST_MakePoint(%(longitude)s, %(latitude)s), 4326) END,
            %(location_status)s, %(location_precision)s, %(geocode_source)s,
            %(coordinate_adjustment_m)s, %(location_review_reason)s, %(is_mappable)s,
            %(moderation_status)s, 'legacy_csv', NOW()
        )
        ON CONFLICT (legacy_id) DO UPDATE SET
            occurred_at = EXCLUDED.occurred_at,
            crime_type = EXCLUDED.crime_type,
            description = EXCLUDED.description,
            reporter_name = EXCLUDED.reporter_name,
            street_name_raw = EXCLUDED.street_name_raw,
            street_name_normalized = EXCLUDED.street_name_normalized,
            latitude = EXCLUDED.latitude,
            longitude = EXCLUDED.longitude,
            latitude_original = EXCLUDED.latitude_original,
            longitude_original = EXCLUDED.longitude_original,
            incident_location = EXCLUDED.incident_location,
            location_status = EXCLUDED.location_status,
            location_precision = EXCLUDED.location_precision,
            geocode_source = EXCLUDED.geocode_source,
            coordinate_adjustment_m = EXCLUDED.coordinate_adjustment_m,
            location_review_reason = EXCLUDED.location_review_reason,
            is_mappable = EXCLUDED.is_mappable,
            moderation_status = EXCLUDED.moderation_status,
            source_name = EXCLUDED.source_name,
            updated_at = NOW()
    """
    with connection.cursor() as cursor:
        for row in dataframe.to_dict("records"):
            is_mappable = _as_bool(row.get("is_mappable"))
            location_status = str(row.get("location_status") or "legacy_unreviewed")
            params = {
                "legacy_id": int(row["id"]),
                "occurred_at": _as_timestamp(row["timestamp"]),
                "crime_type": row["type"],
                "description": str(row.get("description") or ""),
                "reporter_name": _clean_value(row.get("reporter_name")),
                "street_name_raw": _clean_value(row.get("street_name_raw")),
                "street_name_normalized": _clean_value(row.get("street_name_normalized")),
                "latitude": _clean_value(row.get("latitude")),
                "longitude": _clean_value(row.get("longitude")),
                "latitude_original": _clean_value(row.get("latitude_original")),
                "longitude_original": _clean_value(row.get("longitude_original")),
                "location_status": location_status,
                "location_precision": str(row.get("location_precision") or "unknown"),
                "geocode_source": _clean_value(row.get("geocode_source")),
                "coordinate_adjustment_m": _clean_value(row.get("coordinate_adjustment_m")),
                "location_review_reason": _clean_value(row.get("location_review_reason")),
                "is_mappable": is_mappable,
                "moderation_status": _moderation_status(location_status, is_mappable),
            }
            cursor.execute(query, params)
            summary[params["moderation_status"]] += 1
    return len(dataframe), summary


def backup_input_csv(csv_path):
    """Preserve the CSV source before Postgres becomes the dashboard authority."""
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = csv_path.with_name(f"{csv_path.stem}.pre_postgres_migration_{timestamp}{csv_path.suffix}")
    shutil.copy2(csv_path, backup_path)
    return backup_path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default=str(PROJECT_ROOT / "crime_data.csv"), help="CSV hasil audit lokasi.")
    parser.add_argument("--skip-backup", action="store_true", help="Lewati backup CSV sebelum migrasi.")
    args = parser.parse_args()
    csv_path = Path(args.input)
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV tidak ditemukan: {csv_path}")

    started_at = datetime.now()
    backup_path = None if args.skip_backup else backup_input_csv(csv_path)
    with get_connection() as connection:
        apply_schema(connection)
        street_count = import_street_references(connection)
        incident_count, status_summary = import_incidents(connection, csv_path)
        connection.commit()

    print(f"PostGIS schema ready. Streets: {street_count}. Incidents upserted: {incident_count}.")
    if backup_path:
        print(f"CSV backup: {backup_path}")
    print("Moderation status:", dict(status_summary))
    print(f"Completed in {(datetime.now() - started_at).total_seconds():.1f}s")


if __name__ == "__main__":
    main()
