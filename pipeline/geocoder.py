"""Deterministic road-reference geocoding for Bandung Raya incidents."""

from utils.location_quality import street_location_metadata


def geocode_street(street_name):
    """Return audited road-reference metadata or ``None`` for unmappable areas."""
    metadata = street_location_metadata(street_name)
    if metadata is None or not metadata.get("is_mappable", False):
        return None
    return metadata
