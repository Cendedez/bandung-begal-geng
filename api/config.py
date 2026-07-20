"""Application configuration sourced from environment variables."""

from __future__ import annotations

import os


DEFAULT_DATABASE_URL = "postgresql://bandung_crime:bandung_crime_dev@localhost:5434/bandung_crime"


def get_database_url():
    return os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)


def get_cors_origins():
    configured = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")
    return [origin.strip() for origin in configured.split(",") if origin.strip()]


def get_cors_origin_regex():
    """Return an optional allow-list pattern for ephemeral preview frontends."""

    configured = os.getenv("CORS_ORIGIN_REGEX", "").strip()
    return configured or None
