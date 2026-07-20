"""Small Streamlit bridge to the citizen-facing PWA reporting flow."""

from __future__ import annotations

import os

import streamlit as st


def get_report_app_url():
    """Return the public PWA report page without ever writing reports to CSV."""
    return os.getenv("PWA_REPORT_URL", "http://127.0.0.1:3000/lapor")


def render_report_link():
    """Render a direct route to the canonical PWA report form."""
    st.link_button("Lapor", get_report_app_url(), type="primary", use_container_width=True)
