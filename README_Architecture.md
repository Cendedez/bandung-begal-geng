# 🏗️ System Architecture — Bandung Street Crime Dashboard

## Overview

This project is a **multi-source data processing pipeline** connected to an interactive **Streamlit dashboard** for visualizing street crime incidents (*begal* and *geng motor*) in the Bandung and Cimahi areas.

The system ingests unstructured text data from simulated social media posts and news portal articles, extracts structured crime entities using NLP, geocodes street names to precise coordinates, and renders the results on a coordinate-based heatmap.

---

## Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                      DATA SOURCES                               │
│                                                                 │
│  ┌─────────────────────┐    ┌─────────────────────────────┐     │
│  │  Instagram / X      │    │  News Portals               │     │
│  │  (Simulated JSON)   │    │  (Simulated RSS / Scrape)   │     │
│  │                     │    │                             │     │
│  │  sample_social_     │    │  sample_news.json           │     │
│  │  media.json         │    │                             │     │
│  └────────┬────────────┘    └──────────────┬──────────────┘     │
│           │                                │                    │
└───────────┼────────────────────────────────┼────────────────────┘
            │                                │
            ▼                                ▼
┌─────────────────────────────────────────────────────────────────┐
│  STAGE 1: MULTI-SOURCE INGESTION                                │
│                                                                 │
│  social_media.ingest()        news_portal.ingest()              │
│  → List[RawRecord]            → List[RawRecord]                 │
│                                                                 │
│  RawRecord = {source, text, timestamp}                          │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│  STAGE 2: TEXT STANDARDIZATION                                  │
│                                                                 │
│  cleaner.standardize(raw_records)                               │
│                                                                 │
│  • Strip HTML tags                                              │
│  • Remove emoji characters                                      │
│  • Normalize whitespace                                         │
│  • Lowercase for NLP consistency                                │
│  • Deduplicate by MD5 text hash                                 │
│                                                                 │
│  → List[CleanedRecord]                                          │
│  CleanedRecord = {source, clean_text, original_text, timestamp} │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│  STAGE 3: NLP ENTITY EXTRACTION                                 │
│                                                                 │
│  extractor.extract_entities(cleaned_record)                     │
│                                                                 │
│  Mock Mode (Active):                                            │
│  • Keyword matching for crime category:                         │
│    - "begal", "jambret", "rampas" → Begal                      │
│    - "geng motor", "konvoi", "sweeping" → Geng Motor            │
│  • Regex + known street list for street name extraction          │
│                                                                 │
│  LLM Mode (Template Ready):                                     │
│  • Calls Google Gemini API with structured prompt               │
│  • Returns JSON: {crime_category, street_name}                  │
│                                                                 │
│  → ExtractedRecord = {crime_category, street_name, timestamp,   │
│                        source, description}                     │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│  STAGE 4: GEOCODING                                             │
│                                                                 │
│  geocoder.geocode_street(street_name)                           │
│                                                                 │
│  Strategy (in order):                                           │
│  1. Hardcoded fallback table (19 known streets)                 │
│  2. geopy Nominatim API (with 1.1s rate-limit delay)            │
│     Query: "{street_name}, Bandung, Jawa Barat, Indonesia"      │
│                                                                 │
│  → (latitude, longitude) tuple                                  │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│  STAGE 5: STORAGE                                               │
│                                                                 │
│  Append to crime_data.csv                                       │
│                                                                 │
│  Schema:                                                        │
│  id | timestamp | latitude | longitude | type | description |   │
│     | reporter_name                                             │
│                                                                 │
│  • Auto-increments ID from existing max                         │
│  • Preserves all existing records                               │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│  STAGE 6: VISUALIZATION (Streamlit Dashboard)                   │
│                                                                 │
│  streamlit run app.py                                           │
│                                                                 │
│  • Reads crime_data.csv                                         │
│  • Sidebar filters: date range, crime category                  │
│  • PyDeck HeatmapLayer + ScatterplotLayer                       │
│  • Citizen reporting form (appends to CSV)                      │
│  • Metrics: total incidents, begal count, geng motor count      │
└─────────────────────────────────────────────────────────────────┘
```

---

## Project Structure

```
dashboard-begal/
├── app.py                          # Streamlit dashboard entry point
├── crime_data.csv                  # Shared output (pipeline writes, dashboard reads)
├── requirements.txt                # All Python dependencies
├── generate_mock_data.py           # Original mock data generator (500 records)
├── README_Architecture.md          # This file
│
├── components/                     # Streamlit UI components
│   ├── sidebar.py                  #   Date & category filters
│   ├── map_view.py                 #   PyDeck heatmap visualization
│   └── report_form.py              #   Citizen reporting form
│
├── utils/                          # Shared utilities
│   └── data_loader.py              #   CSV loading, filtering, caching
│
├── pipeline/                       # Data processing pipeline
│   ├── __init__.py
│   ├── run_pipeline.py             #   Main orchestrator (entry point)
│   ├── ingestors/
│   │   ├── __init__.py
│   │   ├── social_media.py         #   Simulated Instagram/X ingestion
│   │   └── news_portal.py          #   Simulated news scraping/RSS
│   ├── cleaner.py                  #   Text standardization & dedup
│   ├── extractor.py                #   NLP entity extraction (mock + LLM template)
│   └── geocoder.py                 #   geopy/Nominatim geocoding + fallback
│
└── data/                           # Raw ingestion samples
    ├── sample_social_media.json    #   20 mock social media posts
    └── sample_news.json            #   10 mock news articles
```

---

## How to Run

### Prerequisites

```bash
pip install -r requirements.txt
```

### Run the Data Pipeline

```bash
python -m pipeline.run_pipeline
```

This will:
1. Ingest 20 social media posts + 10 news articles
2. Clean and deduplicate the text
3. Extract crime categories and street names
4. Geocode street names to coordinates
5. Append new records to `crime_data.csv`

### Run the Dashboard

```bash
streamlit run app.py
```

Open `http://localhost:8501` in your browser to view the interactive heatmap.

---

## Technology Stack

| Component         | Technology                          |
|-------------------|-------------------------------------|
| Dashboard         | Streamlit                           |
| Visualization     | PyDeck (HeatmapLayer)               |
| Data Processing   | pandas, numpy                       |
| NLP Extraction    | Keyword matching (mock) / Gemini API (template) |
| Geocoding         | geopy + Nominatim (OpenStreetMap)   |
| Storage           | CSV (pandas)                        |
| Language          | Python 3.8+                         |

---

## Future Improvements

1. **Real LLM Integration**: Swap `extract_entities()` for `extract_entities_llm()` in `extractor.py` using a Google Gemini API key.
2. **Database Storage**: Migrate from CSV to SQLite or PostgreSQL for better concurrency and querying.
3. **Scheduled Ingestion**: Add a cron job or APScheduler to poll for new social media/news data periodically.
4. **Real Data Sources**: Connect to Instagram Graph API, X API v2, and RSS feeds from local news portals.
5. **Paid Geocoding**: Switch to Google Maps Geocoding API or Mapbox for higher rate limits and accuracy.
6. **Authentication**: Add user login for the citizen reporting system.
