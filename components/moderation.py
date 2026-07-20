"""Internal Streamlit workspace for Postgres-backed report moderation."""

from __future__ import annotations

import hmac
import os

import pandas as pd
import pydeck as pdk
import streamlit as st

from utils.postgres_repository import (
    correct_incident_location,
    get_moderation_counts,
    list_location_revisions,
    list_moderation_incidents,
    preview_location_correction,
    search_reportable_roads,
    update_moderation_status,
)


STATUS_LABELS = {
    "pending": "Menunggu",
    "published": "Dipublikasikan",
    "needs_review": "Perlu ditinjau",
    "rejected": "Ditolak",
}
DECISIONS = {
    "Publikasikan": "published",
    "Perlu ditinjau": "needs_review",
    "Tolak": "rejected",
}


def _moderator_name():
    return os.getenv("MODERATOR_NAME", "Moderator Streamlit")


def _require_moderator_access():
    """Authenticate the lightweight internal moderator workspace."""
    configured_password = os.getenv("MODERATOR_PASSWORD")
    if not configured_password:
        st.error("Akses moderasi belum dikonfigurasi. Atur MODERATOR_PASSWORD pada environment.")
        return False
    if st.session_state.get("moderator_authorized"):
        return True

    st.markdown("### Akses moderator")
    with st.form("moderator_login"):
        submitted_password = st.text_input("Password moderator", type="password")
        submitted = st.form_submit_button("Masuk", type="primary", use_container_width=True)
    if submitted:
        if hmac.compare_digest(submitted_password, configured_password):
            st.session_state["moderator_authorized"] = True
            st.rerun()
        st.error("Password moderator tidak cocok.")
    return False


def _format_incident_option(incident):
    occurred_at = incident["occurred_at"].astimezone().strftime("%d %b %Y %H:%M")
    street_name = incident["street_name_normalized"] or incident["street_name_raw"] or "Lokasi belum jelas"
    return f"#{incident['id']} | {incident['crime_type']} | {street_name} | {occurred_at}"


def _render_incident_detail(incident):
    street_name = incident["street_name_normalized"] or incident["street_name_raw"] or "Belum disebutkan"
    first_column, second_column, third_column = st.columns(3)
    first_column.metric("Kategori", incident["crime_type"])
    second_column.metric("Lokasi", "Siap peta" if incident["is_mappable"] else "Belum aman")
    third_column.metric("Sumber", incident["source_name"])
    occurred_at = incident["occurred_at"].astimezone().strftime("%d %B %Y, %H:%M")
    st.caption(f"Kejadian: {occurred_at} | Jalan: {street_name}")
    st.write(incident["description"])
    if incident["location_review_reason"]:
        st.info(f"Catatan lokasi: {incident['location_review_reason']}")
    if incident["moderation_note"]:
        st.caption(f"Catatan moderasi terakhir: {incident['moderation_note']}")


def _format_road_option(road):
    return f"{road['name']} ({road['highway_type']})"


def _render_location_preview(incident, road_match):
    """Compare the current point with the selected OSM road reference."""
    preview_rows = [
        {
            "latitude": road_match["latitude"],
            "longitude": road_match["longitude"],
            "label": "Ruas pilihan",
            "color": [14, 147, 132, 210],
        }
    ]
    if incident["latitude"] is not None and incident["longitude"] is not None:
        preview_rows.append(
            {
                "latitude": incident["latitude"],
                "longitude": incident["longitude"],
                "label": "Titik sebelumnya",
                "color": [217, 45, 32, 210],
            }
        )
    preview_data = pd.DataFrame(preview_rows)
    st.pydeck_chart(
        pdk.Deck(
            map_style="https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",
            initial_view_state=pdk.ViewState(
                latitude=road_match["latitude"],
                longitude=road_match["longitude"],
                zoom=15,
                pitch=0,
            ),
            layers=[
                pdk.Layer(
                    "ScatterplotLayer",
                    data=preview_data,
                    get_position="[longitude, latitude]",
                    get_fill_color="color",
                    get_radius=95,
                    radius_min_pixels=7,
                    radius_max_pixels=13,
                    pickable=True,
                )
            ],
            tooltip={"text": "{label}"},
        ),
        height=280,
        use_container_width=True,
    )
    st.caption("Hijau: ruas pilihan. Merah: titik sebelumnya, bila tersedia.")


def _render_location_correction(incident):
    """Let a moderator select a road, inspect it, and create an audit trail."""
    with st.expander("Perbaiki lokasi", expanded=not incident["is_mappable"]):
        st.caption("Koreksi tidak langsung menerbitkan laporan. Tinjau kembali sebelum publikasi.")
        search_state_key = f"road_search_query_{incident['id']}"
        with st.form(f"road_search_{incident['id']}"):
            road_query_input = st.text_input(
                "Cari ruas jalan Bandung Raya",
                value=st.session_state.get(search_state_key, ""),
                placeholder="Contoh: Ciumbuleuit",
            )
            search_submitted = st.form_submit_button("Cari ruas", use_container_width=True)
        if search_submitted:
            st.session_state[search_state_key] = road_query_input.strip()

        road_query = st.session_state.get(search_state_key, "")
        roads = search_reportable_roads(road_query) if len(road_query.strip()) >= 2 else []
        selected_road = None
        road_match = None
        if len(road_query.strip()) >= 2 and not roads:
            st.info("Tidak ada ruas yang cocok. Coba variasi nama jalan lain.")
        if roads:
            roads_by_id = {road["osm_way_id"]: road for road in roads}
            selected_road_id = st.selectbox(
                "Pilih ruas yang benar",
                options=list(roads_by_id),
                key=f"road_choice_{incident['id']}",
                format_func=lambda road_id: _format_road_option(roads_by_id[road_id]),
            )
            selected_road = roads_by_id[selected_road_id]
            road_match = preview_location_correction(selected_road_id)
            st.success(f"Ruas dipilih: {road_match['street_name_normalized']}")
            _render_location_preview(incident, road_match)

        with st.form(f"location_correction_{incident['id']}"):
            correction_reason = st.text_area(
                "Alasan koreksi lokasi",
                max_chars=500,
                placeholder="Contoh: Narasi menyebut Jalan Ciumbuleuit, bukan titik pusat wilayah.",
            )
            submitted = st.form_submit_button(
                "Simpan koreksi lokasi",
                type="primary",
                use_container_width=True,
                disabled=selected_road is None,
            )
        if not submitted:
            return
        try:
            corrected_incident = correct_incident_location(
                incident["id"],
                selected_road["osm_way_id"],
                correction_reason,
                _moderator_name(),
            )
        except ValueError as error:
            st.error(str(error))
            return

        st.cache_data.clear()
        st.session_state["moderation_feedback"] = (
            f"Lokasi laporan #{corrected_incident['id']} diperbaiki ke "
            f"{corrected_incident['street_name_normalized']}."
        )
        st.rerun()


def _render_location_revision_history(incident_id):
    revisions = list_location_revisions(incident_id)
    if not revisions:
        return
    with st.expander(f"Riwayat koreksi lokasi ({len(revisions)})"):
        for revision in revisions:
            previous_street = revision["previous_location"].get("street_name_normalized") or "Belum jelas"
            corrected_street = revision["corrected_location"].get("street_name_normalized") or "Belum jelas"
            corrected_at = revision["corrected_at"].astimezone().strftime("%d %b %Y, %H:%M")
            st.markdown(f"**{previous_street}** menjadi **{corrected_street}**")
            st.caption(f"{corrected_at} oleh {revision['corrected_by']} | {revision['correction_reason']}")


def render_moderation_workspace():
    """Render the moderation queue. It is intentionally separate from public data."""
    if not _require_moderator_access():
        return

    if feedback := st.session_state.pop("moderation_feedback", None):
        st.toast(feedback)

    toolbar_left, toolbar_right = st.columns([4, 1], vertical_alignment="center")
    with toolbar_left:
        st.markdown("## Moderasi laporan")
        st.caption("Keputusan disimpan ke Postgres. Hanya laporan dipublikasikan yang muncul di peta.")
    with toolbar_right:
        if st.button("Keluar", use_container_width=True):
            st.session_state.pop("moderator_authorized", None)
            st.rerun()

    counts = get_moderation_counts()
    metrics = st.columns(4)
    for column, status in zip(metrics, STATUS_LABELS, strict=True):
        column.metric(STATUS_LABELS[status], counts[status])

    selected_statuses = st.multiselect(
        "Status antrean",
        options=list(STATUS_LABELS),
        default=["pending", "needs_review"],
        format_func=lambda status: STATUS_LABELS[status],
    )
    incidents = list_moderation_incidents(selected_statuses)
    if not incidents:
        st.info("Tidak ada laporan pada antrean yang dipilih.")
        return

    incident_by_id = {incident["id"]: incident for incident in incidents}
    selected_id = st.selectbox(
        "Pilih laporan",
        options=list(incident_by_id),
        format_func=lambda incident_id: _format_incident_option(incident_by_id[incident_id]),
    )
    incident = incident_by_id[selected_id]
    _render_incident_detail(incident)
    _render_location_correction(incident)
    _render_location_revision_history(incident["id"])

    if not incident["is_mappable"]:
        st.warning("Lokasi belum cukup pasti. Laporan ini tidak dapat dipublikasikan hingga lokasi diperbaiki.")

    with st.form(f"moderation_decision_{incident['id']}"):
        decision_label = st.radio("Tindakan", options=list(DECISIONS), horizontal=True)
        moderation_note = st.text_area(
            "Catatan moderator",
            max_chars=500,
            placeholder="Wajib saat menolak laporan agar keputusan dapat diaudit.",
        )
        submitted = st.form_submit_button("Simpan keputusan", type="primary", use_container_width=True)

    if not submitted:
        return

    target_status = DECISIONS[decision_label]
    if target_status == "rejected" and len(moderation_note.strip()) < 10:
        st.error("Isi alasan penolakan minimal 10 karakter.")
        return
    try:
        result = update_moderation_status(
            incident["id"],
            target_status,
            _moderator_name(),
            moderation_note,
        )
    except ValueError as error:
        st.error(str(error))
        return

    st.cache_data.clear()
    moderation_time = result["moderated_at"].astimezone().strftime("%H:%M")
    status_label = STATUS_LABELS[result["moderation_status"]].lower()
    st.success(f"Laporan #{result['id']} ditandai {status_label} pada {moderation_time}.")
    st.rerun()
