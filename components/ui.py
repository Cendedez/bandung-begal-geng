"""Reusable visual building blocks for the dashboard."""

from html import escape

import streamlit as st


def inject_ui_css():
    """Apply the dashboard's visual system and responsive adjustments."""
    st.markdown(
        """
        <style>
        :root {
            --danger: #D92D20;
            --warning: #F79009;
            --accent: #0E9384;
        }

        .block-container { max-width: 1440px; padding: 1rem 0.5rem 1rem; }
        [data-testid="stHeader"] { background: transparent; height: 0; }

        h1 { font-size: 1.8rem; line-height: 1.15; margin-bottom: 0.25rem; margin-top: 0; }
        .dashboard-eyebrow { color: var(--accent); font-size: 0.85rem; font-weight: 700; margin: 0; }
        .filter-summary { align-items: center; opacity: 0.8; display: flex; flex-wrap: wrap; gap: 0.5rem; margin: 0.5rem 0 1rem; }
        .filter-summary strong { font-weight: bold; }
        .filter-chip { background-color: rgba(14, 147, 132, 0.15); border-radius: 999px; color: var(--accent); font-size: 0.82rem; padding: 0.28rem 0.55rem; }

        .metric-grid { display: grid; gap: 0.75rem; grid-template-columns: repeat(3, minmax(0, 1fr)); margin: 0.75rem 0 1.25rem; }
        .metric-card { 
            background-color: rgba(128, 128, 128, 0.05); 
            border: 1px solid rgba(128, 128, 128, 0.2); 
            border-radius: 8px; 
            border-top: 3px solid var(--accent); 
            padding: 1rem; 
        }
        .metric-card.danger { border-top-color: var(--danger); }
        .metric-card.warning { border-top-color: var(--warning); }
        .metric-card span { opacity: 0.7; font-size: 0.85rem; }
        .metric-card strong { display: block; font-size: 1.8rem; line-height: 1.15; margin-top: 0.25rem; }

        [data-testid="stPydeckChart"] { border: 1px solid rgba(128, 128, 128, 0.2); border-radius: 8px; overflow: hidden; }
        button[kind="primary"] { border-radius: 8px; min-height: 44px; }

        @media (max-width: 720px) {
            .block-container { padding: 1rem 0.9rem 2rem; }
            h1 { font-size: 1.75rem; }
            .metric-grid { grid-template-columns: 1fr; }
            [data-testid="stHorizontalBlock"] { flex-wrap: wrap; }
            [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] { flex: 1 1 100% !important; min-width: 100% !important; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_filter_summary(result_count, start_date, end_date, crime_types):
    """Show filter state in the main content, including on mobile."""
    category_label = ", ".join(crime_types) if crime_types else "Semua kategori"
    date_label = f"{start_date:%d %b %Y} - {end_date:%d %b %Y}"
    st.markdown(
        f"""
        <div class="filter-summary" aria-label="Filter aktif">
            <span><strong>{result_count:,}</strong> laporan ditampilkan</span>
            <span class="filter-chip">{escape(date_label)}</span>
            <span class="filter-chip">{escape(category_label)}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_metric_grid(df):
    """Render concise, consistently styled overview metrics."""
    metrics = [
        ("Total laporan", len(df), "neutral"),
        ("Kasus Begal", int(df["type"].eq("Begal").sum()), "danger"),
        ("Geng Motor", int(df["type"].eq("Geng Motor").sum()), "warning"),
    ]
    cards = "".join(
        f'<article class="metric-card {tone}"><span>{label}</span>'
        f"<strong>{value:,}</strong></article>"
        for label, value, tone in metrics
    )
    st.markdown(
        f'<section class="metric-grid" aria-label="Ringkasan laporan">{cards}</section>',
        unsafe_allow_html=True,
    )
