"use client";

import Link from "next/link";
import {
  ArrowLeft,
  CheckCircle2,
  Clock3,
  LoaderCircle,
  MapPinned,
  Send,
  ShieldAlert,
  Navigation,
} from "lucide-react";
import { type FormEvent, useState } from "react";

const API_BASE_URL = "/api";

type CrimeType = "Begal" | "Geng Motor";

type SubmissionResponse = {
  id: number;
  moderation_status: "pending";
};

function localDateTimeValue(date = new Date()) {
  const timezoneOffset = date.getTimezoneOffset() * 60_000;
  return new Date(date.getTime() - timezoneOffset).toISOString().slice(0, 16);
}

function getErrorMessage(payload: unknown) {
  if (!payload || typeof payload !== "object") return "Laporan belum dapat dikirim. Coba lagi sebentar lagi.";
  const detail = (payload as { detail?: unknown }).detail;
  if (typeof detail === "string") return detail;
  if (detail && typeof detail === "object" && "message" in detail && typeof detail.message === "string") return detail.message;
  return "Periksa kembali isian laporan lalu coba kirim lagi.";
}

export default function ReportExperience() {
  const [crimeType, setCrimeType] = useState<CrimeType>("Begal");
  const [occurredAt, setOccurredAt] = useState(() => localDateTimeValue());
  const [latitude, setLatitude] = useState<number | null>(null);
  const [longitude, setLongitude] = useState<number | null>(null);
  const [isGettingLocation, setIsGettingLocation] = useState(false);
  const [locationError, setLocationError] = useState("");
  const [description, setDescription] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState("");
  const [submittedReport, setSubmittedReport] = useState<SubmissionResponse | null>(null);

  const requestLocation = () => {
    setIsGettingLocation(true);
    setLocationError("");
    
    if (!navigator.geolocation) {
      setLocationError("Browser Anda tidak mendukung fitur lokasi GPS.");
      setIsGettingLocation(false);
      return;
    }

    navigator.geolocation.getCurrentPosition(
      (position) => {
        setLatitude(position.coords.latitude);
        setLongitude(position.coords.longitude);
        setLocationError("");
        setIsGettingLocation(false);
      },
      (error) => {
        setIsGettingLocation(false);
        switch (error.code) {
          case error.PERMISSION_DENIED:
            setLocationError("Izin lokasi ditolak. Tolong izinkan akses lokasi di browser Anda.");
            break;
          case error.POSITION_UNAVAILABLE:
            setLocationError("Informasi lokasi tidak tersedia saat ini.");
            break;
          case error.TIMEOUT:
            setLocationError("Waktu pencarian lokasi habis, coba lagi.");
            break;
          default:
            setLocationError("Terjadi kesalahan saat mengambil lokasi.");
            break;
        }
      },
      { enableHighAccuracy: true, timeout: 10000, maximumAge: 0 }
    );
  };

  const resetForm = () => {
    setCrimeType("Begal");
    setOccurredAt(localDateTimeValue());
    setLatitude(null);
    setLongitude(null);
    setLocationError("");
    setDescription("");
    setSubmitError("");
    setSubmittedReport(null);
  };

  const submitReport = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (latitude === null || longitude === null) {
      setSubmitError("Tolong izinkan dan ambil lokasi Anda terlebih dahulu.");
      return;
    }

    setIsSubmitting(true);
    setSubmitError("");
    try {
      const response = await fetch(`${API_BASE_URL}/v1/reports`, {
        method: "POST",
        headers: { 
          "Content-Type": "application/json",
          "ngrok-skip-browser-warning": "true" 
        },
        cache: "no-store",
        body: JSON.stringify({
          crime_type: crimeType,
          occurred_at: occurredAt,
          description: description.trim(),
          latitude: latitude,
          longitude: longitude,
        }),
      });
      const body = (await response.json()) as SubmissionResponse | { detail?: unknown };
      if (!response.ok) throw new Error(getErrorMessage(body));
      setSubmittedReport(body as SubmissionResponse);
    } catch (error) {
      setSubmitError(error instanceof Error ? error.message : "Laporan belum dapat dikirim.");
    } finally {
      setIsSubmitting(false);
    }
  };

  const canSubmit = Boolean(latitude !== null && longitude !== null && occurredAt && description.trim().length >= 20 && !isSubmitting);

  if (submittedReport) {
    return (
      <main className="report-app report-success-app">
        <header className="report-topbar">
          <Link href="/" className="back-link">
            <ArrowLeft size={19} />
            <span>Peta</span>
          </Link>
          <span className="report-brand"><ShieldAlert size={18} /> Bandung Aman</span>
        </header>
        <section className="submission-success" aria-live="polite">
          <span className="success-mark"><CheckCircle2 size={34} /></span>
          <p>Laporan diterima</p>
          <h1>Terima kasih sudah melapor.</h1>
          <strong>#{submittedReport.id}</strong>
          <span>Status: menunggu peninjauan</span>
          <div className="success-actions">
            <button className="secondary-action" type="button" onClick={resetForm}>Buat laporan lain</button>
            <Link className="primary-action report-map-link" href="/">Lihat peta</Link>
          </div>
        </section>
      </main>
    );
  }

  return (
    <main className="report-app">
      <header className="report-topbar">
        <Link href="/" className="back-link">
          <ArrowLeft size={19} />
          <span>Peta</span>
        </Link>
        <span className="report-brand"><ShieldAlert size={18} /> Bandung Aman</span>
      </header>

      <section className="report-content">
        <div className="report-heading">
          <p>Bandung Raya</p>
          <h1>Buat laporan</h1>
        </div>

        <form className="report-form" onSubmit={submitReport}>
          <fieldset className="report-section crime-choice">
            <legend>Jenis kejadian</legend>
            <div className="crime-selector">
              {(["Begal", "Geng Motor"] as CrimeType[]).map((type) => (
                <button
                  className={crimeType === type ? `crime-option ${type === "Begal" ? "begal" : "geng"} is-selected` : "crime-option"}
                  type="button"
                  key={type}
                  onClick={() => setCrimeType(type)}
                  aria-pressed={crimeType === type}
                >
                  {type}
                </button>
              ))}
            </div>
          </fieldset>

          <div className="report-section report-field">
            <label htmlFor="occurred-at"><Clock3 size={18} /> Waktu kejadian</label>
            <input
              id="occurred-at"
              type="datetime-local"
              value={occurredAt}
              max={localDateTimeValue()}
              onChange={(event) => setOccurredAt(event.target.value)}
              required
            />
          </div>

          <div className="report-section report-field road-field">
            <label><MapPinned size={18} /> Lokasi kejadian</label>
            
            <div className="road-check-action" style={{ marginTop: '0.5rem' }}>
              <button 
                className="check-road-button" 
                type="button" 
                onClick={requestLocation} 
                disabled={isGettingLocation}
                style={{ width: '100%', justifyContent: 'center', padding: '1rem' }}
              >
                {isGettingLocation ? <LoaderCircle className="field-spinner" size={19} /> : <Navigation size={19} />}
                {isGettingLocation ? "Mendapatkan lokasi GPS..." : (latitude ? "Perbarui Lokasi GPS Saya" : "Gunakan Lokasi GPS Saya")}
              </button>
            </div>
            
            {locationError && <p className="field-error" role="alert" style={{ marginTop: '0.5rem' }}>{locationError}</p>}
            
            {latitude !== null && longitude !== null && !locationError && (
              <div className="road-match road-match-exact" aria-live="polite" style={{ marginTop: '0.5rem' }}>
                <div className="road-match-heading">
                  <CheckCircle2 size={19} />
                  <strong>Lokasi GPS berhasil diamankan</strong>
                </div>
                <p>Lat: {latitude.toFixed(5)}, Lon: {longitude.toFixed(5)}</p>
                <span>Sistem akan otomatis mencocokkan ke jalan terdekat.</span>
              </div>
            )}
          </div>

          <div className="report-section report-field description-field">
            <label htmlFor="description">Keterangan kejadian</label>
            <textarea
              id="description"
              value={description}
              maxLength={500}
              minLength={20}
              onChange={(event) => setDescription(event.target.value)}
              placeholder="Ceritakan singkat kejadian yang Anda lihat"
              required
            />
            <div className="field-meta">
              <span>Jangan tulis nomor telepon atau email.</span>
              <span>{description.trim().length}/500</span>
            </div>
          </div>

          {submitError && <p className="submit-error" role="alert">{submitError}</p>}

          <div className="report-submit-bar">
            <button className="report-submit" type="submit" disabled={!canSubmit}>
              {isSubmitting ? <LoaderCircle className="field-spinner" size={19} /> : <Send size={19} />}
              {isSubmitting ? "Mengirim laporan" : "Kirim laporan"}
            </button>
          </div>
        </form>
      </section>
    </main>
  );
}
