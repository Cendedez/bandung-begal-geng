from __future__ import annotations

from datetime import date
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    HRFlowable,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "output" / "pdf"
OUT_DIR.mkdir(parents=True, exist_ok=True)
PDF_PATH = OUT_DIR / "bandung_aman_project_handover.pdf"


PAGE_W, PAGE_H = A4
MARGIN_X = 1.55 * cm
MARGIN_Y = 1.4 * cm
CONTENT_W = PAGE_W - (MARGIN_X * 2)


def styles():
    base = getSampleStyleSheet()
    base["Normal"].fontName = "Helvetica"
    base["Normal"].fontSize = 9.2
    base["Normal"].leading = 13
    base["Normal"].textColor = colors.HexColor("#172033")

    return {
        "cover_title": ParagraphStyle(
            "cover_title",
            parent=base["Title"],
            fontName="Helvetica-Bold",
            fontSize=25,
            leading=30,
            textColor=colors.white,
            alignment=TA_LEFT,
            spaceAfter=8,
        ),
        "cover_subtitle": ParagraphStyle(
            "cover_subtitle",
            parent=base["Normal"],
            fontSize=11,
            leading=16,
            textColor=colors.HexColor("#dbeafe"),
            spaceAfter=14,
        ),
        "h1": ParagraphStyle(
            "h1",
            parent=base["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=17,
            leading=22,
            textColor=colors.HexColor("#0f172a"),
            spaceBefore=10,
            spaceAfter=8,
        ),
        "h2": ParagraphStyle(
            "h2",
            parent=base["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=12.5,
            leading=16,
            textColor=colors.HexColor("#111827"),
            spaceBefore=8,
            spaceAfter=5,
        ),
        "body": ParagraphStyle(
            "body",
            parent=base["Normal"],
            fontSize=9.2,
            leading=13,
            spaceAfter=6,
        ),
        "small": ParagraphStyle(
            "small",
            parent=base["Normal"],
            fontSize=8,
            leading=10.5,
            textColor=colors.HexColor("#64748b"),
        ),
        "caption": ParagraphStyle(
            "caption",
            parent=base["Normal"],
            fontSize=7.6,
            leading=9.5,
            textColor=colors.HexColor("#64748b"),
            alignment=TA_CENTER,
        ),
        "callout": ParagraphStyle(
            "callout",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=9.3,
            leading=13.2,
            textColor=colors.HexColor("#0f172a"),
        ),
        "table": ParagraphStyle(
            "table",
            parent=base["Normal"],
            fontSize=7.6,
            leading=9.3,
            textColor=colors.HexColor("#172033"),
        ),
        "table_head": ParagraphStyle(
            "table_head",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=7.5,
            leading=9,
            textColor=colors.white,
        ),
    }


S = styles()


def p(text: str, style: str = "body") -> Paragraph:
    return Paragraph(text, S[style])


def bullet(items: list[str]) -> ListFlowable:
    return [p(f"- {item}", "body") for item in items]


def numbered(items: list[str]) -> ListFlowable:
    return [p(f"{index}. {item}", "body") for index, item in enumerate(items, 1)]


def chip(text: str, fill: str, stroke: str = "#cbd5e1") -> Table:
    table = Table([[p(text, "small")]], colWidths=[None])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(fill)),
                ("BOX", (0, 0), (-1, -1), 0.4, colors.HexColor(stroke)),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    return table


def section(title: str) -> list:
    return [Spacer(1, 4), p(title, "h1"), HRFlowable(width="100%", color=colors.HexColor("#e2e8f0"), thickness=0.8), Spacer(1, 7)]


def table(data, col_widths=None, head_rows=1) -> Table:
    wrapped = []
    for r, row in enumerate(data):
        style = "table_head" if r < head_rows else "table"
        wrapped.append([p(str(cell), style) for cell in row])
    t = Table(wrapped, colWidths=col_widths, repeatRows=head_rows)
    rules = [
        ("BACKGROUND", (0, max(head_rows, 0)), (-1, -1), colors.white),
        ("ROWBACKGROUNDS", (0, max(head_rows, 0)), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#d8dee9")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]
    if head_rows:
        rules.insert(0, ("BACKGROUND", (0, 0), (-1, head_rows - 1), colors.HexColor("#0f172a")))
    t.setStyle(TableStyle(rules))
    return t


def cover(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(colors.HexColor("#0b1220"))
    canvas.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
    canvas.setFillColor(colors.HexColor("#0369a1"))
    canvas.rect(0, PAGE_H - 5.8 * cm, PAGE_W, 5.8 * cm, fill=1, stroke=0)
    canvas.setFillColor(colors.HexColor("#f59e0b"))
    canvas.rect(0, PAGE_H - 5.95 * cm, PAGE_W, 0.15 * cm, fill=1, stroke=0)
    canvas.setFillColor(colors.HexColor("#0ea5e9"))
    canvas.circle(PAGE_W - 1.2 * cm, PAGE_H - 1.15 * cm, 1.25 * cm, fill=1, stroke=0)
    canvas.setFillColor(colors.HexColor("#155e75"))
    canvas.circle(1.1 * cm, PAGE_H - 4.85 * cm, 0.95 * cm, fill=1, stroke=0)
    canvas.restoreState()


def footer(canvas, doc):
    canvas.saveState()
    if doc.page > 1:
        canvas.setStrokeColor(colors.HexColor("#e2e8f0"))
        canvas.line(MARGIN_X, 1.05 * cm, PAGE_W - MARGIN_X, 1.05 * cm)
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(colors.HexColor("#64748b"))
        canvas.drawString(MARGIN_X, 0.65 * cm, "Bandung Aman - Project Handover")
        canvas.drawRightString(PAGE_W - MARGIN_X, 0.65 * cm, f"Page {doc.page}")
    canvas.restoreState()


def cover_page() -> list:
    story = []
    story.append(Spacer(1, 1.65 * cm))
    story.append(p("Bandung Aman", "cover_title"))
    story.append(p("Street Crime Dashboard and Citizen Reporting PWA", "cover_subtitle"))
    story.append(Spacer(1, 0.65 * cm))
    story.append(
        table(
            [
                ["Status", "Beta publik gratis sudah berjalan di Vercel, backend masih lokal/tunnel"],
                ["Target pengguna", "Warga Bandung Raya, terutama akses mobile"],
                ["Wilayah cakupan", "Kota Bandung, Kota Cimahi, Kabupaten Bandung"],
                ["Tanggal dokumen", date.today().strftime("%d %B %Y")],
            ],
            col_widths=[4.2 * cm, CONTENT_W - 4.2 * cm],
            head_rows=0,
        )
    )
    story.append(Spacer(1, 0.6 * cm))
    story.append(
        table(
            [
                ["URL beta PWA", "https://web-theta-pink-72.vercel.app"],
                ["Domain rencana", "bandungaman.web.id"],
                ["Backend beta", "FastAPI lokal via Cloudflare Quick Tunnel"],
                ["Dokumen terkait", "README_Free_Beta.md, README_Vercel.md, README_API.md, README_Staging.md"],
            ],
            col_widths=[4.2 * cm, CONTENT_W - 4.2 * cm],
            head_rows=0,
        )
    )
    story.append(Spacer(1, 0.7 * cm))
    story.append(p("Catatan penting: dokumen ini tidak memuat password, token, API key, atau data rahasia lain. Semua kredensial harus tetap disimpan di environment lokal atau panel hosting.", "small"))
    story.append(PageBreak())
    return story


def build_story() -> list:
    story = cover_page()

    story += section("1. Deskripsi Proyek")
    story.append(p("Bandung Aman adalah aplikasi peta insiden begal dan geng motor untuk Bandung Raya. Tujuan utamanya adalah membantu warga melihat laporan kejadian berbasis lokasi, mengirim laporan baru, dan memberi moderator alat untuk meninjau laporan sebelum tampil ke publik.", "body"))
    story.append(p("Aplikasi ini awalnya berupa dashboard Streamlit, lalu berkembang menjadi arsitektur yang lebih siap mobile: PWA Next.js untuk warga, FastAPI sebagai public API, PostgreSQL/PostGIS untuk data spasial, dan Streamlit sebagai dashboard moderator internal.", "body"))
    story.append(Spacer(1, 4))
    story.append(p("Masalah yang diselesaikan", "h2"))
    story.extend(bullet([
        "Warga butuh peta yang mudah dibuka dari HP untuk melihat laporan rawan begal dan geng motor.",
        "Koordinat tidak boleh asal titik; nama jalan perlu dicocokkan ke ruas jalan yang benar.",
        "Laporan warga tidak boleh langsung tampil publik; harus lewat moderasi.",
        "Sumber data dari teks sosial media atau berita perlu dinormalisasi sebelum menjadi titik peta.",
    ]))

    story += section("2. Stack Saat Ini")
    story.append(
        table(
            [
                ["Komponen", "Teknologi", "Fungsi"],
                ["PWA warga", "Next.js 16, React 19, TypeScript, MapLibre", "Peta mobile, halaman Lapor, installable PWA"],
                ["API publik", "FastAPI, Pydantic", "Endpoint insiden, ruas jalan, road matching, submit laporan"],
                ["Database", "PostgreSQL + PostGIS", "Penyimpanan insiden, laporan, ruas jalan, metadata lokasi"],
                ["Moderator", "Streamlit", "Review, approve, reject, koreksi lokasi laporan"],
                ["Peta legacy", "Streamlit + PyDeck", "Dashboard awal dan visualisasi internal"],
                ["Pipeline data", "Python, pandas, geocoder, cleaner, extractor", "Normalisasi teks, ekstraksi kategori, geocoding"],
                ["Deploy beta", "Vercel + Cloudflare Quick Tunnel", "Frontend publik gratis, backend lokal sementara"],
            ],
            col_widths=[3.1 * cm, 4.3 * cm, CONTENT_W - 7.4 * cm],
        )
    )

    story += section("3. Progres Yang Sudah Selesai")
    story.append(p("Berikut ringkasan progres teknis yang sudah berjalan di repo dan percakapan implementasi terakhir.", "body"))
    story.append(
        table(
            [
                ["Area", "Status", "Catatan"],
                ["UI/UX", "Selesai tahap awal", "Streamlit diperbaiki; PWA mobile-first dibuat untuk warga"],
                ["PWA map", "Selesai", "MapLibre memuat data GeoJSON dari API lewat path /api"],
                ["Halaman Lapor", "Selesai tahap awal", "Form laporan warga dibuat di PWA dan mengirim ke API"],
                ["API FastAPI", "Selesai tahap awal", "Endpoint health, incidents, streets, road search, road match, reports"],
                ["Database PostGIS", "Selesai tahap awal", "Schema dan migrasi dari CSV ke Postgres tersedia"],
                ["Ruas jalan", "Selesai tahap awal", "Importer OSM mencakup Kota Bandung, Kota Cimahi, Kabupaten Bandung"],
                ["Moderasi", "Selesai tahap awal", "Laporan masuk pending; moderator dapat approve/reject/koreksi"],
                ["Vercel", "Selesai", "PWA sudah deploy ke https://web-theta-pink-72.vercel.app"],
                ["Mode gratis", "Selesai", "Panduan README_Free_Beta.md dibuat untuk Vercel + tunnel lokal"],
                ["Staging VPS", "Disiapkan", "Docker Compose, Caddyfile, env example, dan README_Staging.md tersedia"],
            ],
            col_widths=[3.1 * cm, 3.2 * cm, CONTENT_W - 6.3 * cm],
        )
    )

    story += section("4. Status Deploy dan Operasional")
    story.append(p("Status saat dokumen dibuat: PWA sudah dapat diakses publik melalui Vercel. API masih bergantung pada backend lokal yang dipublikasikan lewat Cloudflare Quick Tunnel.", "body"))
    story.extend(bullet([
        "URL beta PWA: https://web-theta-pink-72.vercel.app",
        "Frontend tetap bisa terbuka walau backend mati, tetapi data peta dan submit laporan tidak akan berfungsi.",
        "Cloudflare Quick Tunnel cocok untuk demo dan beta kecil, tetapi URL dapat berubah dan tidak punya jaminan uptime.",
        "Jika tunnel berubah, PWA perlu dideploy ulang dengan INTERNAL_API_URL baru.",
        "Domain bandungaman.web.id adalah pilihan nama yang cocok jika nanti dibeli dan diarahkan ke Vercel.",
    ]))
    story.append(p("Pembagian domain yang direncanakan jika sudah punya domain utama:", "h2"))
    story.append(
        table(
            [
                ["Hostname", "Fungsi", "Tujuan"],
                ["bandungaman.web.id", "PWA warga", "Frontend publik di Vercel"],
                ["www.bandungaman.web.id", "Alias PWA", "Akses umum dengan www"],
                ["api.bandungaman.web.id", "Backend API", "FastAPI di VPS atau home server"],
                ["admin.bandungaman.web.id", "Moderator", "Streamlit internal untuk moderasi"],
            ],
            col_widths=[4.2 * cm, 4 * cm, CONTENT_W - 8.2 * cm],
        )
    )

    story += section("5. Keputusan Penting")
    story.append(
        table(
            [
                ["Topik", "Keputusan", "Alasan"],
                ["Target perangkat", "Mobile-first", "Pengguna utama adalah warga Bandung yang mengakses lewat HP"],
                ["Frontend", "Tetap Next.js PWA", "Lebih layak untuk mobile daripada Streamlit publik"],
                ["Moderator", "Tetap Streamlit", "Cepat untuk admin internal dan tidak perlu UI publik mewah"],
                ["Domain", "Cukup 1 domain", "Subdomain dapat dipakai untuk PWA, API, dan admin"],
                ["Hosting murah cPanel", "Tidak dipakai untuk backend", "Seller menyatakan Python/Django/Node tidak bisa dan menyarankan VPS"],
                ["NordVPN", "Tidak dipakai untuk hosting publik", "VPN bukan server backend publik"],
                ["Laptop bekas", "Bisa untuk home server beta", "Opsi realistis saat budget nol, tapi uptime tergantung listrik/internet rumah"],
                ["X ingestion", "Belum otomatis penuh", "X API resmi berbayar/terbatas; scraping rawan putus"],
            ],
            col_widths=[3.4 * cm, 4.4 * cm, CONTENT_W - 7.8 * cm],
        )
    )

    story += section("6. Risiko dan Batasan")
    story.append(
        table(
            [
                ["Risiko", "Dampak", "Mitigasi"],
                ["Backend lokal mati", "Peta dan form laporan gagal", "Tampilkan status server, fallback WhatsApp/Google Form"],
                ["Tunnel berubah", "Vercel rewrite ke API lama gagal", "Deploy ulang PWA dengan INTERNAL_API_URL baru"],
                ["Data jalan tidak akurat", "Titik peta meleset dari jalan", "Pakai OSM road matching dan label lokasi sebagai referensi ruas"],
                ["Laporan palsu/duplikat", "Peta publik tercemar", "Moderasi wajib, rate limit, dedup, audit trail"],
                ["X API berbayar", "Tidak bisa auto ambil tweet stabil secara gratis", "Mulai dari input link X manual/semi otomatis"],
                ["Home server down", "Layanan publik putus", "UPS kecil, auto-start service, backup harian"],
                ["Data sensitif", "Privasi dan keamanan warga terganggu", "Jangan tampilkan kontak pribadi; sanitasi teks laporan"],
            ],
            col_widths=[3.4 * cm, 4.5 * cm, CONTENT_W - 7.9 * cm],
        )
    )

    story += section("7. Roadmap Sampai Selesai")
    story.append(p("Prioritas roadmap disusun untuk kondisi budget sangat terbatas. Targetnya: aplikasi tetap bisa dipakai, aman, dan berkembang bertahap.", "body"))
    story.append(
        table(
            [
                ["Tahap", "Target", "Output selesai"],
                ["A. Beta Rp0", "Vercel + backend laptop/tunnel", "PWA publik, laporan bisa masuk saat backend aktif, status server jelas"],
                ["B. Home server", "Laptop bekas sebagai server 24 jam", "FastAPI, PostGIS, moderator jalan otomatis di rumah"],
                ["C. Domain", "Hubungkan bandungaman.web.id", "PWA, API, admin memakai subdomain rapi"],
                ["D. Fallback laporan", "Tambahkan WhatsApp/Google Form saat backend offline", "Tidak ada laporan hilang ketika API mati"],
                ["E. X semi otomatis", "Input link tweet ke form/sheet lalu diproses pipeline", "Laporan dari X bisa masuk tanpa API berbayar"],
                ["F. X resmi", "Integrasi X API jika ada budget/API access", "Auto polling keyword dan akun sumber secara stabil"],
                ["G. Produksi murah", "Pindah ke VPS 2GB saat ada dana", "Uptime lebih baik, backup, monitoring, HTTPS permanen"],
            ],
            col_widths=[2.7 * cm, 5.1 * cm, CONTENT_W - 7.8 * cm],
        )
    )

    story += section("8. Tugas Teknis Berikutnya")
    story.append(p("Urutan ini yang paling masuk akal untuk dilanjutkan jika pekerjaan diteruskan oleh AI/developer lain.", "body"))
    story.extend(numbered([
        "Tambahkan indikator status server di PWA. Endpoint /api/health dicek berkala, lalu UI memberi pesan jelas saat backend offline.",
        "Tambahkan fallback laporan: tombol WhatsApp dan/atau Google Form ketika API tidak tersedia.",
        "Siapkan laptop bekas sebagai home server: install Docker, nonaktifkan sleep, jalankan database/API/moderator sebagai service.",
        "Buat backup database harian otomatis ke file SQL dan salin ke lokasi eksternal.",
        "Rapikan deduplikasi data yang terlihat berulang di endpoint incidents; beberapa record lama tampak duplikat.",
        "Tambahkan workflow ingest X semi otomatis berbasis link tweet yang dikirim ke form/sheet.",
        "Jika domain sudah dibeli, arahkan DNS ke Vercel untuk PWA dan ke tunnel/server untuk API/admin.",
        "Buat halaman disclaimer: bukan kanal darurat resmi, data berbasis laporan warga dan perlu verifikasi.",
        "Uji mobile real device: peta, geolocation, submit laporan, install PWA, dan tampilan offline.",
        "Siapkan panduan operator non-teknis untuk moderasi: approve, reject, koreksi titik, dan hapus duplikat.",
    ]))

    story += section("9. Checklist Serah Terima")
    story.append(
        table(
            [
                ["Item", "Status", "Catatan"],
                ["Repo lokal", "Ada", "G:\\Projects\\dashboard-begal"],
                ["Git", "Ada branch main", "Ada perubahan .gitignore dan README_Free_Beta.md belum tentu sudah commit"],
                ["PWA Vercel", "Live", "https://web-theta-pink-72.vercel.app"],
                ["API lokal", "Perlu dinyalakan", "uvicorn api.main:app --host 127.0.0.1 --port 8000"],
                ["Tunnel", "Perlu dinyalakan", "cloudflared tunnel --url http://127.0.0.1:8000"],
                ["Database", "Postgres/PostGIS", "Jangan expose port database ke internet"],
                ["Moderator", "Streamlit", "Password jangan ditulis di dokumen publik"],
                ["Domain", "Belum final", "bandungaman.web.id adalah kandidat tepat"],
                ["Hosting 24 jam", "Belum permanen", "Opsi nol rupiah: laptop bekas sebagai home server"],
            ],
            col_widths=[3.2 * cm, 3.4 * cm, CONTENT_W - 6.6 * cm],
        )
    )

    story += section("10. Perintah Penting")
    story.append(p("Jalankan dari PowerShell di root proyek atau folder web sesuai kebutuhan.", "body"))
    story.append(
        table(
            [
                ["Kebutuhan", "Perintah"],
                ["Cek API lokal", "Invoke-RestMethod http://127.0.0.1:8000/openapi.json"],
                ["Jalankan API lokal", ".\\.venv\\Scripts\\python.exe -m uvicorn api.main:app --host 127.0.0.1 --port 8000"],
                ["Jalankan PWA lokal", "Set-Location G:\\Projects\\dashboard-begal\\web; npm run dev"],
                ["Typecheck PWA", "Set-Location G:\\Projects\\dashboard-begal\\web; npm run typecheck"],
                ["Build PWA", "Set-Location G:\\Projects\\dashboard-begal\\web; npm run build"],
                ["Deploy Vercel tunnel", "npx vercel@latest deploy --prod --yes --build-env INTERNAL_API_URL=https://URL-TUNNEL --env INTERNAL_API_URL=https://URL-TUNNEL"],
                ["Import OSM roads", ".\\.venv\\Scripts\\python.exe -m scripts.import_osm_roads"],
                ["Migrate CSV", ".\\.venv\\Scripts\\python.exe -m scripts.migrate_csv_to_postgres --input crime_data.csv"],
            ],
            col_widths=[4.0 * cm, CONTENT_W - 4.0 * cm],
        )
    )

    story += section("11. Definisi Selesai")
    story.append(p("Proyek bisa dianggap selesai versi beta publik apabila seluruh poin berikut terpenuhi.", "body"))
    story.extend(bullet([
        "PWA bisa dibuka dari domain final atau URL Vercel tanpa error di Android.",
        "Peta memuat insiden published dan memberi label bahwa titik adalah referensi ruas jalan, bukan lokasi presisi korban.",
        "Form Lapor dapat mencari ruas jalan, mengirim laporan, dan memberi feedback status sukses/gagal.",
        "Jika backend offline, pengguna mendapat pesan yang jelas dan fallback laporan tersedia.",
        "Moderator bisa approve, reject, koreksi lokasi, dan membersihkan duplikat.",
        "Database punya backup rutin dan file backup bisa dipulihkan.",
        "Pipeline ingest minimal bisa menerima input manual dari link X atau sumber berita.",
        "Ada disclaimer bahwa aplikasi bukan kanal darurat resmi dan laporan tetap perlu verifikasi.",
    ]))

    story += section("12. Ringkasan Akhir")
    story.append(p("Bandung Aman sudah bergerak dari dashboard Streamlit sederhana menjadi sistem mobile-first dengan PWA, API, database spasial, road matching, dan moderasi. Kendala utama bukan lagi desain awal, tetapi operasional: backend 24 jam, strategi data dari X, backup, dan keamanan.", "body"))
    story.append(p("Dengan budget nol, jalur terbaik adalah Vercel gratis untuk frontend dan laptop bekas sebagai home server untuk backend. Jika nanti ada dana kecil, opsi paling sehat adalah VPS 2GB agar FastAPI, PostGIS, dan moderator tidak bergantung pada laptop pribadi.", "body"))
    return story


def main():
    doc = SimpleDocTemplate(
        str(PDF_PATH),
        pagesize=A4,
        rightMargin=MARGIN_X,
        leftMargin=MARGIN_X,
        topMargin=MARGIN_Y,
        bottomMargin=1.25 * cm,
        title="Bandung Aman Project Handover",
        author="Codex",
        subject="Project summary, progress, roadmap, and handover checklist",
    )
    doc.build(build_story(), onFirstPage=lambda c, d: (cover(c, d), footer(c, d)), onLaterPages=footer)
    print(PDF_PATH)


if __name__ == "__main__":
    main()
