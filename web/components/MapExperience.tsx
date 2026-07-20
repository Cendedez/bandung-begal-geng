"use client";

import type { Feature, FeatureCollection, Point } from "geojson";
import maplibregl, { type GeoJSONSource, type Map as MapLibreMap, type StyleSpecification } from "maplibre-gl";
import Link from "next/link";
import {
  CalendarDays,
  ChevronDown,
  Filter,
  Flame,
  Layers3,
  LocateFixed,
  MapPinned,
  PenLine,
  Search,
  ShieldAlert,
  X,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";


const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "/api";
const BANDUNG_CENTER: [number, number] = [107.6191, -6.9175];

type CrimeType = "Begal" | "Geng Motor";
type MapMode = "combined" | "heat" | "points";

type IncidentProperties = {
  id: number;
  occurred_at: string;
  crime_type: CrimeType;
  street_name: string | null;
  location_precision: string;
};

type IncidentFeature = Feature<Point, IncidentProperties>;
type IncidentCollection = FeatureCollection<Point, IncidentProperties> & { total: number };

type IncidentDetail = IncidentProperties & {
  description: string;
  location_status: string;
  location_review_reason: string | null;
};

type RoadSearchResult = {
  osm_way_id: number;
  name: string;
  highway_type: string;
  latitude: number;
  longitude: number;
};

type Filters = {
  crimeTypes: CrimeType[];
  startDate: string;
  endDate: string;
};

const baseMapStyle: StyleSpecification = {
  version: 8,
  sources: {
    osm: {
      type: "raster",
      tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
      tileSize: 256,
      attribution: "© OpenStreetMap contributors",
      maxzoom: 19,
    },
  },
  layers: [{ id: "osm", type: "raster", source: "osm" }],
};


function formatDate(value: string) {
  return new Intl.DateTimeFormat("id-ID", {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}


function updateMapLayers(map: MapLibreMap, mode: MapMode) {
  const heatVisibility = mode === "points" ? "none" : "visible";
  const pointVisibility = mode === "heat" ? "none" : "visible";
  if (map.getLayer("incidents-heat")) map.setLayoutProperty("incidents-heat", "visibility", heatVisibility);
  if (map.getLayer("incidents-points")) map.setLayoutProperty("incidents-points", "visibility", pointVisibility);
}


export default function MapExperience() {
  const mapContainerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const searchTimerRef = useRef<number | null>(null);
  const skipNextRoadSearchRef = useRef(false);
  const incidentsRef = useRef<IncidentCollection>({ type: "FeatureCollection", features: [], total: 0 });
  const [mapReady, setMapReady] = useState(false);
  const [mode, setMode] = useState<MapMode>("combined");
  const [filters, setFilters] = useState<Filters>({ crimeTypes: ["Begal", "Geng Motor"], startDate: "", endDate: "" });
  const [draftFilters, setDraftFilters] = useState<Filters>({ crimeTypes: ["Begal", "Geng Motor"], startDate: "", endDate: "" });
  const [isFilterOpen, setIsFilterOpen] = useState(false);
  const [incidents, setIncidents] = useState<IncidentCollection>({ type: "FeatureCollection", features: [], total: 0 });
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [selectedIncident, setSelectedIncident] = useState<IncidentDetail | null>(null);
  const [isDetailLoading, setIsDetailLoading] = useState(false);
  const [searchTerm, setSearchTerm] = useState("");
  const [roads, setRoads] = useState<RoadSearchResult[]>([]);
  const [isSearching, setIsSearching] = useState(false);

  const activeFilterCount = Number(filters.crimeTypes.length !== 2) + Number(Boolean(filters.startDate)) + Number(Boolean(filters.endDate));
  const selectedFeature = useMemo(
    () => incidents.features.find((feature) => feature.properties?.id === selectedId) ?? null,
    [incidents.features, selectedId],
  );

  const updateIncidentSource = useCallback((collection: IncidentCollection) => {
    incidentsRef.current = collection;
    const source = mapRef.current?.getSource("incidents") as GeoJSONSource | undefined;
    source?.setData(collection);
  }, []);

  const loadIncidents = useCallback(async (signal?: AbortSignal) => {
    setIsLoading(true);
    setLoadError("");
    const params = new URLSearchParams();
    filters.crimeTypes.forEach((crimeType) => params.append("crime_type", crimeType));
    if (filters.startDate) params.set("start_date", filters.startDate);
    if (filters.endDate) params.set("end_date", filters.endDate);

    try {
      const response = await fetch(`${API_BASE_URL}/v1/incidents?${params.toString()}`, { signal });
      if (!response.ok) throw new Error("Data peta belum tersedia.");
      const collection = (await response.json()) as IncidentCollection;
      setIncidents(collection);
      updateIncidentSource(collection);
    } catch (error) {
      if ((error as Error).name !== "AbortError") setLoadError("Peta tidak dapat memuat laporan saat ini.");
    } finally {
      if (!signal?.aborted) setIsLoading(false);
    }
  }, [filters, updateIncidentSource]);

  useEffect(() => {
    const controller = new AbortController();
    void loadIncidents(controller.signal);
    return () => controller.abort();
  }, [loadIncidents]);

  useEffect(() => {
    if (!mapContainerRef.current || mapRef.current) return;

    const map = new maplibregl.Map({
      container: mapContainerRef.current,
      style: baseMapStyle,
      center: BANDUNG_CENTER,
      zoom: 11.4,
      minZoom: 9.5,
      maxZoom: 18,
      attributionControl: false,
    });
    mapRef.current = map;
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
    map.addControl(new maplibregl.AttributionControl({ compact: true }), "bottom-right");

    map.on("load", () => {
      map.addSource("incidents", { type: "geojson", data: incidentsRef.current });
      map.addLayer({
        id: "incidents-heat",
        type: "heatmap",
        source: "incidents",
        maxzoom: 15,
        paint: {
          "heatmap-weight": ["case", ["==", ["get", "crime_type"], "Begal"], 1, 0.7],
          "heatmap-intensity": ["interpolate", ["linear"], ["zoom"], 10, 0.7, 15, 2],
          "heatmap-color": [
            "interpolate",
            ["linear"],
            ["heatmap-density"],
            0, "rgba(0, 0, 0, 0)",
            0.25, "#f7c66a",
            0.55, "#e98543",
            0.8, "#d94f42",
            1, "#7e2332",
          ],
          "heatmap-radius": ["interpolate", ["linear"], ["zoom"], 10, 18, 15, 42],
          "heatmap-opacity": ["interpolate", ["linear"], ["zoom"], 13, 0.82, 16, 0],
        },
      });
      map.addLayer({
        id: "incidents-points",
        type: "circle",
        source: "incidents",
        minzoom: 11,
        paint: {
          "circle-radius": ["interpolate", ["linear"], ["zoom"], 11, 5, 16, 9],
          "circle-color": ["match", ["get", "crime_type"], "Begal", "#cf4d46", "#ef9a41"],
          "circle-stroke-color": "#ffffff",
          "circle-stroke-width": 1.5,
          "circle-opacity": 0.94,
        },
      });
      map.on("click", "incidents-points", (event) => {
        const incidentId = Number(event.features?.[0]?.properties?.id);
        if (incidentId) setSelectedId(incidentId);
      });
      map.on("mouseenter", "incidents-points", () => {
        map.getCanvas().style.cursor = "pointer";
      });
      map.on("mouseleave", "incidents-points", () => {
        map.getCanvas().style.cursor = "";
      });
      setMapReady(true);
      updateMapLayers(map, mode);
    });

    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, []);

  useEffect(() => {
    if (mapReady && mapRef.current) updateMapLayers(mapRef.current, mode);
  }, [mapReady, mode]);

  useEffect(() => {
    if (!selectedId) {
      setSelectedIncident(null);
      return;
    }
    const controller = new AbortController();
    setIsDetailLoading(true);
    fetch(`${API_BASE_URL}/v1/incidents/${selectedId}`, { signal: controller.signal })
      .then((response) => {
        if (!response.ok) throw new Error("Detail tidak tersedia.");
        return response.json() as Promise<IncidentDetail>;
      })
      .then((detail) => setSelectedIncident(detail))
      .catch(() => setSelectedIncident(null))
      .finally(() => {
        if (!controller.signal.aborted) setIsDetailLoading(false);
      });
    return () => controller.abort();
  }, [selectedId]);

  useEffect(() => {
    if (searchTimerRef.current) window.clearTimeout(searchTimerRef.current);
    if (skipNextRoadSearchRef.current) {
      skipNextRoadSearchRef.current = false;
      setIsSearching(false);
      return;
    }
    const term = searchTerm.trim();
    if (term.length < 2) {
      setRoads([]);
      setIsSearching(false);
      return;
    }
    setIsSearching(true);
    searchTimerRef.current = window.setTimeout(() => {
      fetch(`${API_BASE_URL}/v1/roads/search?q=${encodeURIComponent(term)}`)
        .then((response) => (response.ok ? response.json() as Promise<RoadSearchResult[]> : []))
        .then(setRoads)
        .catch(() => setRoads([]))
        .finally(() => setIsSearching(false));
    }, 260);
    return () => {
      if (searchTimerRef.current) window.clearTimeout(searchTimerRef.current);
    };
  }, [searchTerm]);

  const chooseRoad = (road: RoadSearchResult) => {
    mapRef.current?.flyTo({ center: [road.longitude, road.latitude], zoom: 15.5, essential: true });
    skipNextRoadSearchRef.current = true;
    setSearchTerm(road.name);
    setRoads([]);
  };

  const locateBandung = () => {
    mapRef.current?.flyTo({ center: BANDUNG_CENTER, zoom: 11.4, essential: true });
  };

  const toggleCrime = (crimeType: CrimeType) => {
    setDraftFilters((current) => ({
      ...current,
      crimeTypes: current.crimeTypes.includes(crimeType)
        ? current.crimeTypes.filter((type) => type !== crimeType)
        : [...current.crimeTypes, crimeType],
    }));
  };

  const resetFilters = () => setDraftFilters({ crimeTypes: ["Begal", "Geng Motor"], startDate: "", endDate: "" });

  return (
    <main className="map-app">
      <div ref={mapContainerRef} className="map-canvas" aria-label="Peta laporan keamanan Bandung Raya" />

      <header className="map-header">
        <div className="brand-lockup">
          <span className="brand-mark"><ShieldAlert size={20} strokeWidth={2.3} /></span>
          <div>
            <p>Bandung Raya</p>
            <h1>Bandung Aman</h1>
          </div>
        </div>
        <button className="icon-button" type="button" onClick={locateBandung} aria-label="Kembali ke Bandung Raya" title="Kembali ke Bandung Raya">
          <LocateFixed size={20} />
        </button>
      </header>

      <section className="map-toolbar" aria-label="Kontrol peta">
        <label className="road-search">
          <Search size={19} aria-hidden="true" />
          <input
            value={searchTerm}
            onChange={(event) => setSearchTerm(event.target.value)}
            placeholder="Cari jalan"
            aria-label="Cari jalan di Bandung Raya"
          />
          {isSearching && <span className="search-pulse" aria-label="Mencari" />}
        </label>
        {roads.length > 0 && (
          <ul className="road-results" aria-label="Hasil pencarian jalan">
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
      </section>

      <div className="map-mode-control" aria-label="Mode peta">
        <button className={mode === "combined" ? "is-active" : ""} type="button" onClick={() => setMode("combined")} aria-label="Tampilan gabungan" title="Tampilan gabungan">
          <Layers3 size={19} />
        </button>
        <button className={mode === "heat" ? "is-active" : ""} type="button" onClick={() => setMode("heat")} aria-label="Tampilan heatmap" title="Heatmap">
          <Flame size={19} />
        </button>
        <button className={mode === "points" ? "is-active" : ""} type="button" onClick={() => setMode("points")} aria-label="Tampilan titik" title="Titik kejadian">
          <MapPinned size={19} />
        </button>
      </div>

      <button className="filter-trigger" type="button" onClick={() => {
        setDraftFilters(filters);
        setIsFilterOpen(true);
      }}>
        <Filter size={19} />
        <span>Filter</span>
        {activeFilterCount > 0 && <b>{activeFilterCount}</b>}
        <ChevronDown size={16} />
      </button>

      <Link className="report-trigger" href="/lapor" aria-label="Buat laporan baru">
        <PenLine size={19} />
        <span>Lapor</span>
      </Link>

      <div className="map-status" aria-live="polite">
        {isLoading ? "Memuat laporan..." : loadError || `${incidents.total} laporan tervalidasi`}
      </div>

      {isFilterOpen && (
        <section className="sheet-backdrop" role="dialog" aria-modal="true" aria-label="Filter peta">
          <div className="filter-sheet">
            <div className="sheet-handle" />
            <div className="sheet-heading">
              <div>
                <p>Sesuaikan peta</p>
                <h2>Filter laporan</h2>
              </div>
              <button className="icon-button" type="button" onClick={() => setIsFilterOpen(false)} aria-label="Tutup filter" title="Tutup">
                <X size={20} />
              </button>
            </div>
            <div className="filter-group">
              <span>Kategori</span>
              <div className="filter-options">
                {(["Begal", "Geng Motor"] as CrimeType[]).map((crimeType) => (
                  <button
                    key={crimeType}
                    className={draftFilters.crimeTypes.includes(crimeType) ? `filter-option ${crimeType === "Begal" ? "begal" : "geng"} is-selected` : "filter-option"}
                    type="button"
                    onClick={() => toggleCrime(crimeType)}
                  >
                    {crimeType}
                  </button>
                ))}
              </div>
            </div>
            <div className="filter-group">
              <span><CalendarDays size={17} /> Periode</span>
              <div className="date-inputs">
                <label>
                  <small>Mulai</small>
                  <input type="date" value={draftFilters.startDate} onChange={(event) => setDraftFilters((current) => ({ ...current, startDate: event.target.value }))} />
                </label>
                <label>
                  <small>Sampai</small>
                  <input type="date" value={draftFilters.endDate} onChange={(event) => setDraftFilters((current) => ({ ...current, endDate: event.target.value }))} />
                </label>
              </div>
            </div>
            <div className="sheet-actions">
              <button className="text-action" type="button" onClick={resetFilters}>Atur ulang</button>
              <button className="primary-action" type="button" onClick={() => {
                setFilters(draftFilters);
                setIsFilterOpen(false);
              }}>Terapkan</button>
            </div>
          </div>
        </section>
      )}

      {selectedId && (
        <section className="incident-sheet" aria-live="polite">
          <button className="sheet-close" type="button" onClick={() => setSelectedId(null)} aria-label="Tutup detail laporan" title="Tutup">
            <X size={19} />
          </button>
          <div className="sheet-handle" />
          {isDetailLoading && <p className="detail-loading">Memuat detail laporan...</p>}
          {!isDetailLoading && selectedIncident && (
            <>
              <div className="incident-kicker">
                <span className={selectedIncident.crime_type === "Begal" ? "incident-dot begal" : "incident-dot geng"} />
                {selectedIncident.crime_type}
              </div>
              <h2>{selectedIncident.street_name ?? selectedFeature?.properties?.street_name ?? "Lokasi terverifikasi"}</h2>
              <time>{formatDate(selectedIncident.occurred_at)}</time>
              <p className="incident-description">{selectedIncident.description}</p>
              <p className="location-note">Lokasi menunjukkan referensi ruas jalan, bukan titik kejadian presisi.</p>
            </>
          )}
          {!isDetailLoading && !selectedIncident && <p className="detail-loading">Detail laporan tidak tersedia.</p>}
        </section>
      )}
    </main>
  );
}
