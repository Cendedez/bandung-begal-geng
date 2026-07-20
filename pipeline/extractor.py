"""Crime and street entity extraction with strict location evidence."""

from __future__ import annotations

import re

from utils.location_quality import load_street_references


BEGAL_KEYWORDS = [
    "begal",
    "bajing loncat",
    "jambret",
    "rampas",
    "rampok",
    "dirampas",
    "merampas",
    "perampasan",
]
GENG_MOTOR_KEYWORDS = [
    "geng motor",
    "konvoi",
    "sweeping",
    "kelompok motor",
    "gerombolan motor",
    "rusuh",
    "onar",
    "bentrok",
]
OUT_OF_SCOPE_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in ("kutai timur", "kalimantan timur", "jakarta", "surabaya", "medan")
]


def _normalize_text(value):
    return re.sub(r"[^a-z0-9]+", " ", str(value).lower()).strip()


def _classify_crime(text):
    text_lower = text.lower()
    for keyword in BEGAL_KEYWORDS:
        if keyword in text_lower:
            return "Begal"
    for keyword in GENG_MOTOR_KEYWORDS:
        if keyword in text_lower:
            return "Geng Motor"
    return None


def is_out_of_scope(text):
    """Reject explicit references outside the Bandung Raya monitoring area."""
    return any(pattern.search(text) for pattern in OUT_OF_SCOPE_PATTERNS)


def extract_street_details(text):
    """Extract only catalogued street names with explicit street evidence."""
    normalized_text = _normalize_text(text)
    candidates = []

    for canonical_name, reference in load_street_references().items():
        aliases = sorted(reference.get("aliases", []), key=len, reverse=True)
        for alias in aliases:
            normalized_alias = _normalize_text(alias)
            match = re.search(
                rf"\b(?:jl|jalan)\s+{re.escape(normalized_alias)}\b",
                normalized_text,
            )
            if match:
                candidates.append((match.start(), -len(normalized_alias), canonical_name, alias))

        for alias in reference.get("landmark_aliases", []):
            normalized_alias = _normalize_text(alias)
            match = re.search(rf"\b{re.escape(normalized_alias)}\b", normalized_text)
            if match:
                candidates.append((match.start(), -len(normalized_alias), canonical_name, alias))

    if not candidates:
        return None

    _, _, canonical_name, matched_alias = min(candidates)
    return {
        "street_name": canonical_name,
        "matched_alias": matched_alias,
    }


def _extract_street_name(text):
    """Compatibility wrapper used by existing code and audit scripts."""
    details = extract_street_details(text)
    return details["street_name"] if details else None


def extract_entities(cleaned_record):
    """Extract crime and a verified street candidate from a source record."""
    clean_text = cleaned_record.get("clean_text", "")
    original_text = cleaned_record.get("original_text", clean_text)

    category = _classify_crime(clean_text)
    if category is None or is_out_of_scope(original_text):
        return None

    street_details = extract_street_details(original_text)
    if street_details is None:
        return None

    return {
        "crime_category": category,
        "street_name": street_details["street_name"],
        "street_name_raw": street_details["matched_alias"],
        "timestamp": cleaned_record.get("timestamp", ""),
        "source": cleaned_record.get("source", "unknown"),
        "description": original_text,
    }


def extract_entities_llm(cleaned_record, api_key=None):
    """Reserved for a structured LLM extractor with the same output schema."""
    raise NotImplementedError("LLM extraction is not configured for this project.")
