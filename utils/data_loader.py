"""Postgres loading and DataFrame filtering for dashboard records."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from utils.location_quality import ensure_location_columns, is_mappable_record
from utils.postgres_repository import load_published_incidents


BASE_COLUMNS = ["id", "timestamp", "latitude", "longitude", "type", "description", "reporter_name"]


def _parse_mappable(value):
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"true", "1", "yes"}


@st.cache_data(ttl=30, show_spinner=False)
def load_data():
    """Load published, map-safe records from Postgres for the public dashboard."""
    df = load_published_incidents()
    for column in BASE_COLUMNS:
        if column not in df.columns:
            df[column] = pd.NA
    df = ensure_location_columns(df)
    df["is_mappable"] = df["is_mappable"].map(_parse_mappable)
    return df


def filter_data(df, start_date, end_date, crime_types):
    """Filter records by date range and selected crime categories."""
    if df.empty:
        return df

    valid_timestamps = df["timestamp"].notna()
    mask = valid_timestamps & (df["timestamp"].dt.date >= start_date) & (df["timestamp"].dt.date <= end_date)
    filtered_df = df.loc[mask]
    if crime_types:
        filtered_df = filtered_df[filtered_df["type"].isin(crime_types)]
    return filtered_df.copy()


def filter_mappable_data(df):
    """Return only records safe to render as incident markers or heatmap input."""
    if df.empty:
        return df
    mask = is_mappable_record(df) & df["latitude"].notna() & df["longitude"].notna()
    return df.loc[mask].copy()

