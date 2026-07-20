# Public Map API (Day 1)

FastAPI dan PostGIS ini menjadi sumber data untuk aplikasi warga. Streamlit saat ini tetap berjalan terpisah sebagai dashboard internal.

## Jalankan lokal

```powershell
docker compose up -d database
.\.venv\Scripts\python.exe -m pip install -r requirements-api.txt
.\.venv\Scripts\python.exe -m scripts.migrate_csv_to_postgres --input crime_data.csv
.\.venv\Scripts\python.exe -m uvicorn api.main:app --host 127.0.0.1 --port 8000
```

Dokumentasi interaktif tersedia di `http://127.0.0.1:8000/docs`.

## Endpoint publik

- `GET /health` memeriksa koneksi PostGIS.
- `GET /v1/incidents` mengembalikan GeoJSON titik yang sudah `published` dan `is_mappable`.
- `GET /v1/incidents/{id}` mengembalikan detail dari titik yang sudah publik.
- `GET /v1/streets` mengembalikan katalog jalan yang dapat dipilih pada form laporan.
- `GET /v1/roads/search?q=rajawali` mencari ruas OSM dalam tiga wilayah Bandung Raya.
- `POST /v1/road-match` memeriksa nama atau ruas jalan yang dipilih sebelum laporan dikirim.
- `POST /v1/reports` menerima laporan warga sebagai `pending`; laporan tidak pernah masuk peta publik sampai moderator menerbitkannya.

Contoh filter peta:

```text
/v1/incidents?crime_type=Begal&start_date=2026-07-01&end_date=2026-07-31&west=107.58&south=-6.93&east=107.60&north=-6.90
```

Data dengan status lokasi ambigu, perlu peninjauan, atau di luar Bandung Raya tetap disimpan dalam database untuk moderator, tetapi tidak pernah dikirim oleh endpoint publik. Ganti password dan `DATABASE_URL` sebelum deployment.

Master ruas jalan mencakup Kota Bandung, Kota Cimahi, dan Kabupaten Bandung. Jalankan importer berikut saat inisialisasi atau pembaruan data OSM:

```powershell
.\.venv\Scripts\python.exe -m scripts.import_osm_roads
```

Ruas OSM yang diimpor adalah kandidat pencarian jalan. Katalog `street_references` tetap menjadi sumber titik referensi yang telah diaudit untuk pelaporan otomatis.

## Alur laporan warga

Kirim nama jalan ke `POST /v1/road-match` terlebih dahulu. Hasil `exact` atau `alias_match` dapat membawa titik referensi; hasil `ambiguous` dan `needs_review` sengaja tidak diberi titik dan harus dipilih atau diperiksa moderator. Untuk pilihan jalan dari pencarian, kirimkan juga `road_way_id` agar ruas OSM menjadi sumber lokasi yang otoritatif.

`POST /v1/reports` menerapkan batas lima laporan per alamat IP dalam 15 menit, menolak nomor telepon atau email pada keterangan, menolak waktu kejadian di masa depan, dan menahan laporan duplikat. Semua laporan baru memakai `moderation_status = pending`, termasuk yang nama jalannya cocok tepat. Endpoint publik hanya membaca data `published` dan `is_mappable`.
