# Free Beta Deployment Tanpa Domain

Mode ini cocok untuk uji publik awal tanpa biaya domain dan tanpa VPS.

## Arsitektur

- PWA warga: Vercel gratis, memakai URL `*.vercel.app`.
- API dan database: tetap berjalan di laptop lokal.
- Akses API publik sementara: Cloudflare Quick Tunnel `*.trycloudflare.com`.

## Batasan Penting

- Laptop harus tetap menyala.
- Backend API lokal harus tetap berjalan di `http://127.0.0.1:8000`.
- Proses `cloudflared` harus tetap hidup.
- URL `*.trycloudflare.com` bisa berubah saat tunnel dimatikan atau dibuat ulang.
- Kalau URL tunnel berubah, PWA perlu dideploy ulang dengan `INTERNAL_API_URL` baru.

## Langkah Ulang Deploy

Jalankan dari PowerShell.

1. Pastikan API lokal hidup:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/openapi.json
```

2. Siapkan `cloudflared` sementara jika belum terpasang:

```powershell
$toolDir = Join-Path $env:TEMP 'dashboard-begal-tools'
$toolPath = Join-Path $toolDir 'cloudflared.exe'
New-Item -ItemType Directory -Path $toolDir -Force | Out-Null
if (-not (Test-Path $toolPath)) {
    Invoke-WebRequest -Uri 'https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe' -OutFile $toolPath
}
& $toolPath --version
```

3. Jalankan tunnel:

```powershell
& $toolPath tunnel --url http://127.0.0.1:8000 --no-autoupdate
```

Ambil URL yang berbentuk:

```text
https://nama-acak.trycloudflare.com
```

4. Deploy PWA ke Vercel dengan URL tunnel:

```powershell
Set-Location G:\Projects\dashboard-begal\web
npx vercel@latest deploy --prod --yes --build-env INTERNAL_API_URL=https://nama-acak.trycloudflare.com --env INTERNAL_API_URL=https://nama-acak.trycloudflare.com
```

5. Tes URL Vercel:

```powershell
curl.exe -I https://nama-project.vercel.app
curl.exe https://nama-project.vercel.app/api/v1/incidents
```

## Kapan Perlu Naik Kelas

Mode ini cukup untuk demo dan beta kecil. Untuk warga Bandung yang mulai banyak mengakses, pindahkan API dan database ke hosting permanen supaya tidak bergantung pada laptop lokal.
