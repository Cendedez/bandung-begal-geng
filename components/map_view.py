"""PyDeck map rendering for the crime dashboard."""

import html
import json
import os
from pathlib import Path

import pandas as pd
import pydeck as pdk
import streamlit as st


MAP_STYLES = {
    "Gelap": "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json",
    "Terang": "https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",
    "Satelit": "mapbox://styles/mapbox/satellite-streets-v12",
}
BOUNDARY_PATH = Path(__file__).resolve().parents[1] / "data" / "boundaries.geojson"
LOCATION_STATUS_LABELS = {
    "street_verified": "Titik jalan terverifikasi",
    "street_reference": "Referensi ruas jalan",
    "manual_coordinate": "Koordinat pelapor",
}


@st.cache_data(show_spinner=False)
def _load_boundaries():
    if not BOUNDARY_PATH.exists():
        return None
    try:
        with BOUNDARY_PATH.open("r", encoding="utf-8") as boundary_file:
            return json.load(boundary_file)
    except (OSError, json.JSONDecodeError):
        return None


def _incident_color(crime_type):
    return [217, 45, 32, 190] if crime_type == "Begal" else [247, 144, 9, 190]


def render_map(df, map_theme="Gelap", layer_mode="Gabungan", show_boundaries=True):
    """Render heatmap and incident layers without mutating the source dataframe."""
    if df.empty:
        st.info("Tidak ada laporan untuk kombinasi filter ini.")
        return

    display_df = df.dropna(subset=["latitude", "longitude"]).copy()
    if display_df.empty:
        st.info("Laporan yang dipilih belum memiliki koordinat yang dapat dipetakan.")
        return

    timestamp = pd.to_datetime(display_df["timestamp"], errors="coerce")
    display_df["timestamp_str"] = timestamp.dt.strftime("%d %b %Y, %H:%M").fillna("Tidak diketahui")
    display_df["type_safe"] = (
        display_df["type"].fillna("Tidak diketahui").astype(str).map(html.escape)
    )
    display_df["description_safe"] = (
        display_df["description"].fillna("").astype(str).str.slice(0, 180).map(html.escape)
    )
    display_df["street_safe"] = (
        display_df["street_name_normalized"].fillna("Tidak disebutkan").astype(str).map(html.escape)
    )
    display_df["location_status_safe"] = (
        display_df["location_status"]
        .map(LOCATION_STATUS_LABELS)
        .fillna("Status lokasi tidak diketahui")
        .map(html.escape)
    )
    display_df["color"] = display_df["type"].map(_incident_color)

    heatmap_layer = pdk.Layer(
        "HeatmapLayer",
        data=display_df,
        get_position=["longitude", "latitude"],
        get_weight=1,
        aggregation="SUM",
        opacity=0.78,
        radius_pixels=48,
    )
    scatter_layer = pdk.Layer(
        "ScatterplotLayer",
        data=display_df,
        id="incident-points",
        get_position=["longitude", "latitude"],
        get_color="color",
        get_radius=160,
        radius_min_pixels=4,
        radius_max_pixels=16,
        pickable=True,
        auto_highlight=True,
    )

    layers = []
    if show_boundaries and (boundary_data := _load_boundaries()) is not None:
        layers.append(
            pdk.Layer(
                "GeoJsonLayer",
                boundary_data,
                filled=False,
                stroked=True,
                get_line_color=[14, 147, 132, 180],
                get_line_width=28,
                line_width_min_pixels=2,
            )
        )
    if layer_mode in ("Gabungan", "Heatmap"):
        layers.append(heatmap_layer)
    if layer_mode in ("Gabungan", "Titik"):
        layers.append(scatter_layer)

    selected_style = MAP_STYLES.get(map_theme, MAP_STYLES["Gelap"])
    deck_options = {
        "layers": layers,
        "initial_view_state": pdk.ViewState(
            latitude=-6.9147,
            longitude=107.6098,
            zoom=10.7,
            pitch=35,
        ),
        "map_style": selected_style,
        "tooltip": {
            "html": "<b>{type_safe}</b><br/>{timestamp_str}<br/>"
            "Jalan: {street_safe}<br/>Status: {location_status_safe}<br/><br/>{description_safe}",
            "style": {"backgroundColor": "#172033", "color": "#FFFFFF", "maxWidth": "280px"},
        },
    }
    if map_theme == "Satelit" and (mapbox_token := os.getenv("MAPBOX_API_KEY")):
        deck_options["api_keys"] = {"mapbox": mapbox_token}

    map_event = st.pydeck_chart(
        pdk.Deck(**deck_options), 
        use_container_width=True, 
        height=720,
        on_select="rerun",
        selection_mode="single-object",
    )
    return map_event
