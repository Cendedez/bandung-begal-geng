"use client";

import Link from "next/link";
import {
  ArrowLeft,
  BadgeCheck,
  CheckCircle2,
  CircleAlert,
  Clock3,
  LoaderCircle,
  MapPinned,
  Search,
  Send,
  ShieldAlert,
} from "lucide-react";
import { type FormEvent, useEffect, useRef, useState } from "react";


const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "/api";

type CrimeType = "Begal" | "Geng Motor";

type RoadSearchResult = {
  osm_way_id: number;
  name: string;
  highway_type: string;
  latitude: number;
  longitude: number;
};

type RoadMatchCandidate = RoadSearchResult & {
  score: number | null;
};

type RoadMatch = {
  status: "exact" | "alias_match" | "ambiguous" | "needs_review";
  confidence: number;
  street_name_normalized: string | null;
  road_way_id: number | null;
  location_precision: string;
  geocode_source: string;
  review_reason: string;
  candidates: RoadMatchCandidate[];
};

type SubmissionResponse = {
  id: number;
  moderation_status: "pending";
  road_match: RoadMatch;
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


function matchTitle(match: RoadMatch) {
  if (match.status === "exact") return "Ruas jalan terpilih";
  if (match.status === "alias_match") return "Nama jalan terverifikasi";
  if (match.status === "ambiguous") return "Pilih ruas jalan";
  return "Nama jalan perlu ditinjau";
}


export default function ReportExperience() {
  const searchTimerRef = useRef<number | null>(null);
  const [crimeType, setCrimeType] = useState<CrimeType>("Begal");
  const [occurredAt, setOccurredAt] = useState(() => localDateTimeValue());
  const [roadName, setRoadName] = useState("");
  const [roadWayId, setRoadWayId] = useState<number | null>(null);
  const [roads, setRoads] = useState<RoadSearchResult[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [roadMatch, setRoadMatch] = useState<RoadMatch | null>(null);
  const [roadMatchError, setRoadMatchError] = useState("");
  const [isCheckingRoad, setIsCheckingRoad] = useState(false);
  const [description, setDescription] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState("");
  const [submittedReport, setSubmittedReport] = useState<SubmissionResponse | null>(null);

  useEffect(() => {
    if (searchTimerRef.current) window.clearTimeout(searchTimerRef.current);
    const term = roadName.trim();
    if (term.length < 2 || roadWayId !== null) {
      setRoads([]);
      setIsSearching(false);
      return;
    }

    const controller = new AbortController();
    setIsSearching(true);
    searchTimerRef.current = window.setTimeout(() => {
      fetch(`${API_BASE_URL}/v1/roads/search?q=${encodeURIComponent(term)}`, { signal: controller.signal })
        .then((response) => (response.ok ? response.json() as Promise<RoadSearchResult[]> : []))
        .then((results) => setRoads(results.slice(0, 5)))
        .catch((error: Error) => {
          if (error.name !== "AbortError") setRoads([]);
        })
        .finally(() => {
          if (!controller.signal.aborted) setIsSearching(false);
        });
    }, 260);

    return () => {
      controller.abort();
      if (searchTimerRef.current) window.clearTimeout(searchTimerRef.current);
    };
  }, [roadName, roadWayId]);

  const checkRoad = async (name = roadName, wayId = roadWayId) => {
    const normalizedName = name.trim();
    if (normalizedName.length < 2) {
      setRoadMatchError("Isi nama jalan terlebih dahulu.");
      return;
    }
    setIsCheckingRoad(true);
    setRoadMatchError("");
    setRoadMatch(null);
    setRoads([]);
    try {
      const response = await fetch(`${API_BASE_URL}/v1/road-match`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ road_name: normalizedName, ...(wayId ? { road_way_id: wayId } : {}) }),
      });
      if (!response.ok) throw new Error("Lokasi jalan belum dapat diperiksa.");
      setRoadMatch((await response.json()) as RoadMatch);
    } catch (error) {
      setRoadMatchError(error instanceof Error ? error.message : "Lokasi jalan belum dapat diperiksa.");
    } finally {
      setIsCheckingRoad(false);
    }
  };

  const changeRoadName = (value: string) => {
    setRoadName(value);
    setRoadWayId(null);
    setRoadMatch(null);
    setRoadMatchError("");
  };

  const chooseRoad = (road: RoadSearchResult) => {
    setRoadName(road.name);
    setRoadWayId(road.osm_way_id);
    setRoads([]);
    void checkRoad(road.name, road.osm_way_id);
  };

  const resetForm = () => {
    setCrimeType("Begal");
    setOccurredAt(localDateTimeValue());
    setRoadName("");
    setRoadWayId(null);
    setRoads([]);
    setRoadMatch(null);
    setRoadMatchError("");
    setDescription("");
    setSubmitError("");
    setSubmittedReport(null);
  };

  const submitReport = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!roadMatch) {
      setSubmitError("Periksa lokasi jalan sebelum mengirim laporan.");
      return;
    }

    setIsSubmitting(true);
    setSubmitError("");
    try {
      const response = await fetch(`${API_BASE_URL}/v1/reports`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          crime_type: crimeType,
          occurred_at: occurredAt,
          description: description.trim(),
          road_name: roadName.trim(),
          ...(roadWayId ? { road_way_id: roadWayId } : {}),
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

  const canSubmit = Boolean(roadMatch && occurredAt && description.trim().length >= 20 && !isSubmitting);

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
            <label htmlFor="road-name"><MapPinned size={18} /> Nama jalan</label>
            <div className="report-road-input">
              <Search size={19} aria-hidden="true" />
              <input
                id="road-name"
                value={roadName}
                onChange={(event) => changeRoadName(event.target.value)}
                placeholder="Contoh: Jalan Ciumbuleuit"
                autoComplete="off"
                required
              />
              {isSearching && <LoaderCircle className="field-spinner" size={18} aria-label="Mencari jalan" />}
            </div>
            {roads.length > 0 && (
              <ul className="report-road-results" aria-label="Hasil pencarian jalan">
                {roads.map((road) => (
                  <li key={road.osm_way_id}>
                    <button type="button" onClick={() => chooseRoad(road)}>
                      <MapPinned size={17} />
                      <span>{road.name}</span>
                      <small>{road.highway_type}</small>
                    </button>
                  </li>
                ))}
              </ul>
            )}
            <div className="road-check-action">
              <button className="check-road-button" type="button" onClick={() => void checkRoad()} disabled={isCheckingRoad || roadName.trim().length < 2}>
                {isCheckingRoad ? <LoaderCircle className="field-spinner" size={17} /> : <BadgeCheck size={17} />}
                {isCheckingRoad ? "Memeriksa" : "Periksa jalan"}
              </button>
              {roadWayId !== null && <span>Ruas dipilih</span>}
            </div>
            {roadMatchError && <p className="field-error" role="alert">{roadMatchError}</p>}
            {roadMatch && (
              <div className={`road-match road-match-${roadMatch.status}`} aria-live="polite">
                <div className="road-match-heading">
                  {roadMatch.status === "needs_review" ? <CircleAlert size={19} /> : <BadgeCheck size={19} />}
                  <strong>{matchTitle(roadMatch)}</strong>
                </div>
                {roadMatch.street_name_normalized && <p>{roadMatch.street_name_normalized}</p>}
                <span>{roadMatch.review_reason}</span>
                {roadMatch.status === "ambiguous" && roadMatch.candidates.length > 0 && (
                  <ul className="match-candidates">
                    {roadMatch.candidates.map((candidate) => (
                      <li key={candidate.osm_way_id}>
                        <button type="button" onClick={() => chooseRoad(candidate)}>
                          <MapPinned size={16} />
                          <span>{candidate.name}</span>
                          <small>Pilih</small>
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
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
