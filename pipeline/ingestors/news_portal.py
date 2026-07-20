"""
News Portal Ingestor
--------------------
Scrapes recent news articles about street crimes from top Indonesian news portals
(Detik, Kompas, Tribun).
"""

import requests
from bs4 import BeautifulSoup
from datetime import datetime
import time

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Accept-Language': 'id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7'
}

def fetch_and_parse(url, source_name):
    """Generic function to fetch a URL and extract text from common tags."""
    records = []
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Find all potential article titles (usually in h2, h3, or a tags)
            for tag in soup.find_all(['h2', 'h3', 'a']):
                text = tag.get_text(strip=True)
                # Filter out very short texts or navigation links
                if len(text) > 40 and ('begal' in text.lower() or 'geng motor' in text.lower() or 'bandung' in text.lower()):
                    # Find a nearby paragraph for description if available
                    desc = ""
                    sibling_p = tag.find_next_sibling('p')
                    if sibling_p:
                        desc = sibling_p.get_text(strip=True)
                        
                    records.append({
                        "source": f"news_{source_name}",
                        "text": f"{text}. {desc}",
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    })
    except Exception as e:
        print(f"[News Portal] {source_name} scrape error: {e}")
        
    return records

def ingest():
    """
    Scrape news portals and return a list of standardized raw records.
    """
    records = []
    keywords = [
        "begal+bandung", "geng+motor+bandung", 
        "begal+kabupaten+bandung", "geng+motor+kabupaten+bandung",
        "begal+soreang", "geng+motor+soreang",
        "begal+majalaya", "geng+motor+majalaya",
        "begal+baleendah", "geng+motor+baleendah",
        "begal+banjaran", "pembegalan+bandung"
    ]
    
    print("[News Portal Ingestor] Starting live scraping...")
    
    for kw in keywords:
        # Define scraping targets
        targets = [
            ("Detik", f"https://www.detik.com/search/searchall?query={kw}"),
            ("Kompas", f"https://search.kompas.com/search/?q={kw}"),
            ("Tribunnews", f"https://www.tribunnews.com/search?q={kw}"),
            ("TVOne", f"https://www.tvonenews.com/cari?q={kw}"),
            ("CNN", f"https://www.cnnindonesia.com/search/?query={kw}"),
            ("MetroTV", f"https://www.medcom.id/search?q={kw}"),
            ("Liputan6", f"https://www.liputan6.com/search?q={kw}"),
            ("Tempo", f"https://www.tempo.co/search?q={kw}"),
            ("Kumparan", f"https://kumparan.com/search/{kw.replace('+', '%20')}"),
            ("Sindonews", f"https://search.sindonews.com/search?q={kw}")
        ]
        
        for name, url in targets:
            print(f"  Scraping {name} for '{kw}'...")
            records.extend(fetch_and_parse(url, name))
            time.sleep(1)

    print(f"[News Portal Ingestor] Scraped {len(records)} potential articles.")
    return records
