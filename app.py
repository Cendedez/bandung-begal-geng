"""Internal Streamlit dashboard for published incidents and moderation."""

import streamlit as st

from components.map_view import render_map
from components.moderation import render_moderation_workspace
from components.report_form import render_report_link
from components.sidebar import render_sidebar
from components.ui import inject_ui_css, render_filter_summary, render_metric_grid
from utils.data_loader import filter_data, filter_mappable_data, load_data


st.set_page_config(
    page_title="Bandung Crime Dashboard",
    layout="wide",
    initial_sidebar_state="collapsed",
)


def _render_header(min_date, max_date):
    title_col, report_col, moderation_col, filter_col = st.columns(
        [4, 1.6, 1.6, 2], vertical_alignment="bottom"
    )
    with title_col:
        st.markdown(
            '<p class="dashboard-eyebrow">WILAYAH BANDUNG RAYA</p>',
            unsafe_allow_html=True,
        )
        st.title("Street Crime Tracker")
    with report_col:
        render_report_link()
    with moderation_col:
        if st.button("Moderasi", use_container_width=True):
            st.session_state["active_workspace"] = "moderation"
            st.rerun()
    with filter_col:
        return render_sidebar(min_date, max_date)


def _render_recent_reports(dataframe):
    if dataframe.empty:
        return
    recent = dataframe.sort_values("timestamp", ascending=False).head(25).copy()
    recent["Waktu"] = recent["timestamp"].dt.strftime("%d %b %Y, %H:%M")
    recent["Keterangan"] = recent["description"].fillna("").astype(str).str.slice(0, 140)
    recent = recent.rename(columns={"type": "Kategori", "location_status": "Status lokasi"})
    st.dataframe(
        recent[["Waktu", "Kategori", "Status lokasi", "Keterangan"]],
        use_container_width=True,
        hide_index=True,
    )


@st.dialog("Detail kasus")
def _show_incident_details(record):
    """Show a readable case summary for a selected public map point."""
    st.markdown(f"### {record.get('type_safe', 'Tidak diketahui')}")
    st.caption(f"Waktu: {record.get('timestamp_str')} | Pelapor: {record.get('reporter_name', 'Anonim')}")
    st.info(f"Lokasi: {record.get('street_safe')} ({record.get('location_status_safe')})")
    st.write(record.get("description_safe", "Tidak ada keterangan tambahan."))


def _render_dashboard():
    dataframe = load_data()
    min_date = dataframe["timestamp"].dt.date.min() if not dataframe.empty else None
    max_date = dataframe["timestamp"].dt.date.max() if not dataframe.empty else None
    start_date, end_date, selected_crimes, map_theme = _render_header(min_date, max_date)

    if dataframe.empty:
        st.info("Belum ada laporan dipublikasikan untuk ditampilkan di peta.")
        return

    filtered_dataframe = filter_data(dataframe, start_date, end_date, selected_crimes)
    mappable_dataframe = filter_mappable_data(filtered_dataframe)
    excluded_count = len(filtered_dataframe) - len(mappable_dataframe)

    control_col, boundary_col = st.columns([4, 1], vertical_alignment="center")
    with control_col:
        layer_mode = st.segmented_control(
            "Tampilan peta",
            options=["Gabungan", "Heatmap", "Titik"],
            default="Gabungan",
            selection_mode="single",
            label_visibility="collapsed",
        )
    with boundary_col:
        show_boundaries = st.toggle("Batas wilayah", value=True)

    map_event = render_map(
        mappable_dataframe,
        map_theme=map_theme,
        layer_mode=layer_mode or "Gabungan",
        show_boundaries=show_boundaries,
    )
    if map_event and map_event.selection and map_event.selection.get("objects"):
        objects = map_event.selection["objects"]
        if "incident-points" in objects and objects["incident-points"]:
            _show_incident_details(objects["incident-points"][0])

    if excluded_count:
        st.caption(f"{excluded_count} laporan tidak ditampilkan karena lokasi belum spesifik.")

    with st.expander("Lihat ringkasan dan riwayat laporan", expanded=False):
        render_filter_summary(len(filtered_dataframe), start_date, end_date, selected_crimes)
        render_metric_grid(filtered_dataframe)
        _render_recent_reports(filtered_dataframe)


def main():
    inject_ui_css()
    if st.session_state.get("active_workspace") == "moderation":
        if st.button("Kembali ke peta"):
            st.session_state["active_workspace"] = "dashboard"
            st.rerun()
        render_moderation_workspace()
        return
    _render_dashboard()


if __name__ == "__main__":
    main()
