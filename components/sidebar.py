"""Sidebar filters for the crime dashboard."""

import datetime as dt
import os

import streamlit as st


DEFAULT_CRIME_TYPES = ["Begal", "Geng Motor"]


def _date_bounds(min_date, max_date):
    if min_date is None or max_date is None:
        max_date = dt.date.today()
        min_date = max_date - dt.timedelta(days=30)
    elif min_date == max_date:
        min_date = min_date - dt.timedelta(days=1)
    return min_date, max_date


def render_sidebar(min_date, max_date):
    """Render filters with explicit defaults and a reset action."""
    min_date, max_date = _date_bounds(min_date, max_date)
    theme_options = ["Gelap", "Terang"]
    if os.getenv("MAPBOX_API_KEY"):
        theme_options.append("Satelit")

    if "date_range" not in st.session_state:
        st.session_state["date_range"] = (min_date, max_date)
    if "crime_types" not in st.session_state or not set(
        st.session_state["crime_types"]
    ).issubset(DEFAULT_CRIME_TYPES):
        st.session_state["crime_types"] = DEFAULT_CRIME_TYPES.copy()
    if st.session_state.get("map_theme") not in theme_options:
        st.session_state["map_theme"] = "Gelap"

    def reset_filters():
        st.session_state["date_range"] = (min_date, max_date)
        st.session_state["crime_types"] = DEFAULT_CRIME_TYPES.copy()
        st.session_state["map_theme"] = "Gelap"

    with st.popover("⚙️ Filter & Tampilan", use_container_width=True):
        st.caption("Persempit laporan yang terlihat di peta.")

        date_range = st.date_input(
            "Rentang tanggal",
            min_value=min_date,
            max_value=max_date,
            key="date_range",
        )
        crime_types = st.multiselect(
            "Kategori kejadian",
            options=DEFAULT_CRIME_TYPES,
            key="crime_types",
            placeholder="Semua kategori",
            help="Kosong berarti semua kategori ditampilkan.",
        )
        map_theme = st.segmented_control(
            "Gaya peta",
            options=theme_options,
            selection_mode="single",
            key="map_theme",
        )

        st.button(
            "Reset filter",
            use_container_width=True,
            on_click=reset_filters,
        )
        st.divider()
        st.caption(
            "Data bersifat indikatif dari laporan yang dikumpulkan, bukan "
            "notifikasi darurat atau data kepolisian terverifikasi."
        )

    if isinstance(date_range, (tuple, list)) and len(date_range) == 2:
        start_date, end_date = date_range
    else:
        start_date = end_date = date_range[0]

    return start_date, end_date, crime_types, map_theme
