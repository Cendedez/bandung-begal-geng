"""Migrate legacy CSV coordinates to audited street-reference locations."""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

import pandas as pd


sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.extractor import extract_street_details, is_out_of_scope
from utils.location_quality import ensure_location_columns, street_location_metadata


LEGACY_VERIFIED_POINTS = {
    "Jl. Asia Afrika": [(-6.9219, 107.6100)],
    "Jl. BKR": [
        (-6.938102, 107.617561),
        (-6.937619, 107.606196),
        (-6.937537, 107.606410),
    ],
    "Jl. Cihampelas": [(-6.8940, 107.6040)],
    "Jl. Dago": [(-6.8850, 107.6140)],
}


def _as_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _is_verified_legacy_point(street_name, latitude, longitude):
    if latitude is None or longitude is None:
        return False
    for expected_latitude, expected_longitude in LEGACY_VERIFIED_POINTS.get(street_name, []):
        if abs(latitude - expected_latitude) <= 0.00002 and abs(longitude - expected_longitude) <= 0.00002:
            return True
    return False


def repair_dataframe(df):
    """Return a repaired copy plus a summary of its location decisions."""
    repaired = ensure_location_columns(df)
    summary = Counter()

    for index, row in repaired.iterrows():
        existing_status = str(row.get("location_status", ""))
        if existing_status in {"street_verified", "street_reference", "manual_coordinate"}:
            summary["already_processed"] += 1
            continue

        latitude = _as_float(row.get("latitude"))
        longitude = _as_float(row.get("longitude"))
        if pd.isna(row.get("latitude_original")):
            repaired.at[index, "latitude_original"] = latitude
        if pd.isna(row.get("longitude_original")):
            repaired.at[index, "longitude_original"] = longitude

        description = str(row.get("description", ""))
        if is_out_of_scope(description):
            repaired.at[index, "location_status"] = "out_of_scope"
            repaired.at[index, "location_precision"] = "none"
            repaired.at[index, "geocode_source"] = "text_scope_validation"
            repaired.at[index, "location_review_reason"] = "Narasi menyebut lokasi di luar Bandung Raya."
            repaired.at[index, "is_mappable"] = False
            summary["out_of_scope"] += 1
            continue

        details = extract_street_details(description)
        if details is None:
            repaired.at[index, "location_status"] = "unverified_text"
            repaired.at[index, "location_precision"] = "none"
            repaired.at[index, "geocode_source"] = "strict_text_extractor"
            repaired.at[index, "location_review_reason"] = "Narasi tidak menyebut ruas jalan yang dapat diverifikasi."
            repaired.at[index, "is_mappable"] = False
            summary["unverified_text"] += 1
            continue

        street_name = details["street_name"]
        repaired.at[index, "street_name_raw"] = details["matched_alias"]
        metadata = street_location_metadata(street_name, latitude, longitude)
        if metadata is None:
            repaired.at[index, "location_status"] = "needs_review"
            repaired.at[index, "location_precision"] = "none"
            repaired.at[index, "geocode_source"] = "street_reference"
            repaired.at[index, "location_review_reason"] = "Jalan belum tersedia di katalog referensi."
            repaired.at[index, "is_mappable"] = False
            summary["needs_review"] += 1
            continue

        for key, value in metadata.items():
            repaired.at[index, key] = value

        if not metadata.get("is_mappable", False):
            summary[metadata["location_status"]] += 1
            continue

        if _is_verified_legacy_point(street_name, latitude, longitude):
            repaired.at[index, "latitude"] = latitude
            repaired.at[index, "longitude"] = longitude
            repaired.at[index, "location_status"] = "street_verified"
            repaired.at[index, "location_precision"] = "street"
            repaired.at[index, "geocode_source"] = "legacy_osm_audit"
            repaired.at[index, "coordinate_adjustment_m"] = 0.0
            repaired.at[index, "location_review_reason"] = "Koordinat lama telah cocok dengan ruas jalan pada audit OSM."
            summary["street_verified"] += 1
        else:
            summary["street_reference"] += 1

    return repaired, summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default="crime_data.csv", help="CSV yang akan diperiksa.")
    parser.add_argument("--apply", action="store_true", help="Simpan hasil dan buat backup CSV asli.")
    args = parser.parse_args()

    csv_path = Path(args.input)
    source = pd.read_csv(csv_path)
    repaired, summary = repair_dataframe(source)
    print(f"Input rows: {len(source)}")
    for status, count in sorted(summary.items()):
        print(f"  {status}: {count}")

    if not args.apply:
        print("Dry run selesai. Jalankan dengan --apply untuk menyimpan perubahan.")
        return

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = csv_path.with_name(f"{csv_path.stem}.before_location_repair_{timestamp}{csv_path.suffix}")
    shutil.copy2(csv_path, backup_path)
    temporary_path = csv_path.with_suffix(".repairing.csv")
    repaired.to_csv(temporary_path, index=False)
    os.replace(temporary_path, csv_path)
    print(f"Backup created: {backup_path}")
    print(f"Repaired CSV saved: {csv_path}")


if __name__ == "__main__":
    main()
