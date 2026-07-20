"""Street-reference lookup and location-quality helpers."""

from __future__ import annotations

import json
import math
from functools import lru_cache
from pathlib import Path

import pandas as pd


REFERENCE_PATH = Path(__file__).resolve().parents[1] / "data" / "street_reference.json"
MAPPABLE_STATUSES = {"street_verified", "street_reference", "manual_coordinate"}
LOCATION_COLUMNS = {
    "latitude_original": pd.NA,
    "longitude_original": pd.NA,
    "street_name_raw": "",
    "street_name_normalized": "",
    "location_status": "legacy_unreviewed",
    "location_precision": "unknown",
    "geocode_source": "",
    "coordinate_adjustment_m": pd.NA,
    "location_review_reason": "",
    "is_mappable": True,
}


@lru_cache(maxsize=1)
def load_street_references():
    """Return the audited street catalog keyed by its canonical name."""
    with REFERENCE_PATH.open("r", encoding="utf-8") as reference_file:
        payload = json.load(reference_file)
    return {street["canonical_name"]: street for street in payload["streets"]}


def get_street_reference(street_name):
    return load_street_references().get(street_name)


def get_reportable_streets():
    return [
        name
        for name, reference in load_street_references().items()
        if reference.get("mappable", False)
    ]


def haversine_m(latitude_a, longitude_a, latitude_b, longitude_b):
    """Calculate a distance in meters between two latitude/longitude pairs."""
    if any(pd.isna(value) for value in (latitude_a, longitude_a, latitude_b, longitude_b)):
        return None

    earth_radius_m = 6_371_000
    latitude_delta = math.radians(latitude_b - latitude_a)
    longitude_delta = math.radians(longitude_b - longitude_a)
    start_latitude = math.radians(latitude_a)
    end_latitude = math.radians(latitude_b)
    haversine = (
        math.sin(latitude_delta / 2) ** 2
        + math.cos(start_latitude)
        * math.cos(end_latitude)
        * math.sin(longitude_delta / 2) ** 2
    )
    return 2 * earth_radius_m * math.asin(math.sqrt(haversine))


def street_location_metadata(street_name, latitude_original=None, longitude_original=None):
    """Build quality metadata for a canonical street-reference coordinate."""
    reference = get_street_reference(street_name)
    if not reference:
        return None
    if not reference.get("mappable", False):
        return {
            "street_name_normalized": street_name,
            "location_status": "area_only",
            "location_precision": "area",
            "geocode_source": "street_reference",
            "coordinate_adjustment_m": pd.NA,
            "location_review_reason": reference.get("reason", "Nama lokasi tidak dapat dipetakan otomatis."),
            "is_mappable": False,
        }

    adjustment_m = haversine_m(
        latitude_original,
        longitude_original,
        reference["latitude"],
        reference["longitude"],
    )
    return {
        "latitude": reference["latitude"],
        "longitude": reference["longitude"],
        "street_name_normalized": street_name,
        "location_status": "street_reference",
        "location_precision": "road_reference",
        "geocode_source": "osm_nominatim_reference",
        "coordinate_adjustment_m": round(adjustment_m, 1) if adjustment_m is not None else pd.NA,
        "location_review_reason": "Koordinat merepresentasikan ruas jalan, bukan titik kejadian presisi.",
        "is_mappable": True,
    }


def ensure_location_columns(df):
    """Ensure old and newly ingested records share the location-quality schema."""
    prepared = df.copy()
    for column, default in LOCATION_COLUMNS.items():
        if column not in prepared.columns:
            prepared[column] = default
    return prepared


def is_mappable_record(df):
    if "is_mappable" not in df.columns:
        return pd.Series(True, index=df.index)
    return df["is_mappable"].map(
        lambda value: value if isinstance(value, bool) else str(value).strip().lower() in {"true", "1", "yes"}
    )
