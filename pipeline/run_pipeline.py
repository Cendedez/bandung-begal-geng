"""Run ingestion, strict entity extraction, and audited road-reference geocoding."""

from __future__ import annotations

import hashlib
import os
import sys
from datetime import datetime

import pandas as pd


sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.cleaner import standardize
from pipeline.extractor import extract_entities
from pipeline.geocoder import geocode_street
from pipeline.ingestors import news_portal, social_media
from utils.location_quality import ensure_location_columns


OUTPUT_CSV = "crime_data.csv"


def _fingerprint(description):
    normalized = " ".join(str(description).lower().split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _next_id(df):
    if df.empty:
        return 1
    ids = pd.to_numeric(df["id"], errors="coerce").dropna()
    return int(ids.max()) + 1 if not ids.empty else 1


def run():
    """Execute the pipeline without creating unverified map markers."""
    print("=" * 60)
    print("  STREET CRIME DATA PIPELINE")
    print(f"  Started at: {datetime.now():%Y-%m-%d %H:%M:%S}")
    print("=" * 60)

    social_records = social_media.ingest()
    news_records = news_portal.ingest()
    all_raw_records = social_records + news_records
    print(f"[INGEST] Raw records: {len(all_raw_records)}")
    if not all_raw_records:
        return

    cleaned_records = standardize(all_raw_records)
    print(f"[CLEAN] Clean records: {len(cleaned_records)}")
    if not cleaned_records:
        return

    extracted_records = [result for record in cleaned_records if (result := extract_entities(record))]
    print(f"[EXTRACT] Street-qualified records: {len(extracted_records)}")
    if not extracted_records:
        return

    geocoded_records = []
    for record in extracted_records:
        location = geocode_street(record["street_name"])
        if location:
            geocoded_records.append({**record, **location})
    print(f"[GEO] Audited road references: {len(geocoded_records)}")
    if not geocoded_records:
        return

    existing_df = pd.read_csv(OUTPUT_CSV) if os.path.exists(OUTPUT_CSV) else pd.DataFrame()
    existing_df = ensure_location_columns(existing_df)
    existing_fingerprints = set(existing_df["description"].fillna("").map(_fingerprint)) if not existing_df.empty else set()

    new_rows = []
    duplicate_count = 0
    next_id = _next_id(existing_df)
    for record in geocoded_records:
        fingerprint = _fingerprint(record["description"])
        if fingerprint in existing_fingerprints:
            duplicate_count += 1
            continue
        existing_fingerprints.add(fingerprint)
        new_rows.append(
            {
                "id": next_id + len(new_rows),
                "timestamp": record["timestamp"],
                "latitude": record["latitude"],
                "longitude": record["longitude"],
                "type": record["crime_category"],
                "description": record["description"],
                "reporter_name": record["source"],
                "latitude_original": pd.NA,
                "longitude_original": pd.NA,
                "street_name_raw": record["street_name_raw"],
                "street_name_normalized": record["street_name_normalized"],
                "location_status": record["location_status"],
                "location_precision": record["location_precision"],
                "geocode_source": record["geocode_source"],
                "coordinate_adjustment_m": record["coordinate_adjustment_m"],
                "location_review_reason": record["location_review_reason"],
                "is_mappable": record["is_mappable"],
            }
        )

    if new_rows:
        new_df = pd.DataFrame(new_rows)
        combined_df = pd.concat([existing_df, new_df], ignore_index=True)
        combined_df.to_csv(OUTPUT_CSV, index=False)
    else:
        combined_df = existing_df

    print(f"[SAVE] Added: {len(new_rows)} | Duplicate skipped: {duplicate_count}")
    print(f"[SAVE] Total records: {len(combined_df)}")


if __name__ == "__main__":
    run()
