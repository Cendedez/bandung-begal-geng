"""
Text Cleaner
-------------
Standardizes and cleans raw text records from multiple sources.
Removes HTML tags, emoji, excessive whitespace, and deduplicates
records based on text content hashing.
"""

import re
import hashlib


def _strip_html(text):
    """Remove HTML tags from text."""
    return re.sub(r"<[^>]+>", "", text)


def _strip_emoji(text):
    """Remove emoji characters from text."""
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"  # emoticons
        "\U0001F300-\U0001F5FF"  # symbols & pictographs
        "\U0001F680-\U0001F6FF"  # transport & map symbols
        "\U0001F1E0-\U0001F1FF"  # flags
        "\U00002702-\U000027B0"
        "\U000024C2-\U0001F251"
        "\U0001f926-\U0001f937"
        "\U00010000-\U0010ffff"
        "\u2640-\u2642"
        "\u2600-\u2B55"
        "\u200d"
        "\u23cf"
        "\u23e9"
        "\u231a"
        "\ufe0f"
        "\u3030"
        "]+",
        flags=re.UNICODE,
    )
    return emoji_pattern.sub("", text)


def _normalize_whitespace(text):
    """Collapse multiple whitespace characters into single spaces."""
    return re.sub(r"\s+", " ", text).strip()


def _text_hash(text):
    """Generate an MD5 hash of the text for deduplication."""
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def standardize(raw_records):
    """
    Clean and standardize a list of raw text records.

    Steps:
        1. Strip HTML tags
        2. Strip emoji
        3. Normalize whitespace
        4. Lowercase the text (for consistent NLP matching)
        5. Deduplicate by text hash

    Args:
        raw_records: List of dicts with keys: source, text, timestamp.

    Returns:
        list[dict]: Cleaned records with keys: source, clean_text, timestamp.
    """
    seen_hashes = set()
    cleaned = []

    for record in raw_records:
        text = record.get("text", "")

        # Step 1-3: Clean text
        text = _strip_html(text)
        text = _strip_emoji(text)
        text = _normalize_whitespace(text)

        # Step 4: Lowercase for NLP
        clean_text = text.lower()

        # Step 5: Deduplicate
        h = _text_hash(clean_text)
        if h in seen_hashes:
            continue
        seen_hashes.add(h)

        cleaned.append({
            "source": record.get("source", "unknown"),
            "clean_text": clean_text,
            "original_text": text,  # Keep original casing for display
            "timestamp": record.get("timestamp", ""),
        })

    print(f"[Text Cleaner] Cleaned {len(cleaned)} records ({len(raw_records) - len(cleaned)} duplicates removed).")
    return cleaned
