"""Generate internally consistent sample incidents from the street catalog."""

from __future__ import annotations

import random
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

from utils.location_quality import get_reportable_streets, street_location_metadata


NUM_RECORDS = 500
CRIME_TYPES = ["Begal", "Geng Motor"]


def generate_random_date(start_date, end_date):
    """Generate a random datetime between two datetime objects."""
    total_seconds = int((end_date - start_date).total_seconds())
    return start_date + timedelta(seconds=random.randrange(total_seconds))


def generate_dataframe(num_records=NUM_RECORDS, now=None):
    """Build sample records whose coordinates match their stated road."""
    random.seed(42)
    end_date = now or datetime.now()
    start_date = end_date - timedelta(days=180)
    streets = get_reportable_streets()
    records = []

    for incident_id in range(1, num_records + 1):
        street_name = random.choice(streets)
        location = street_location_metadata(street_name)
        crime_type = random.choice(CRIME_TYPES)
        records.append(
            {
                "id": incident_id,
                "timestamp": generate_random_date(start_date, end_date).strftime("%Y-%m-%d %H:%M:%S"),
                "latitude": location["latitude"],
                "longitude": location["longitude"],
                "type": crime_type,
                "description": f"Laporan {crime_type.lower()} di {street_name}.",
                "reporter_name": f"Anon{incident_id}",
                "latitude_original": pd.NA,
                "longitude_original": pd.NA,
                "street_name_raw": street_name,
                "street_name_normalized": street_name,
                "location_status": "street_reference",
                "location_precision": "road_reference",
                "geocode_source": "sample_street_reference",
                "coordinate_adjustment_m": pd.NA,
                "location_review_reason": "Data contoh memakai titik referensi ruas jalan.",
                "is_mappable": True,
            }
        )

    return pd.DataFrame(records).sort_values(by="timestamp").reset_index(drop=True)


def main():
    dataframe = generate_dataframe()
    output_path = Path("crime_data.csv")
    dataframe.to_csv(output_path, index=False)
    print(f"Successfully generated {len(dataframe)} consistent sample records: {output_path}")


if __name__ == "__main__":
    main()
