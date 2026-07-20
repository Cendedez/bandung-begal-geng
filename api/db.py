"""Small psycopg connection helpers for the API and migration tools."""

from __future__ import annotations

from contextlib import contextmanager

import psycopg
from psycopg.rows import dict_row

from api.config import get_database_url


@contextmanager
def get_connection():
    with psycopg.connect(get_database_url(), row_factory=dict_row) as connection:
        yield connection
