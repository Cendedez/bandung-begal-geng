"""
Social Media Ingestor
---------------------
Ingests data from X (Twitter) using the Official API (Tweepy).
If API credentials are not found, it falls back to reading
from a local JSON file that mimics API responses to ensure the pipeline doesn't crash.
"""

import json
import os
import tweepy
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables (like TWITTER_BEARER_TOKEN)
load_dotenv()

# Path to mock social media data (relative to project root)
DEFAULT_DATA_PATH = os.path.join("data", "sample_social_media.json")


def fetch_from_twitter_api():
    """Fetch live data from X using Tweepy."""
    bearer_token = os.environ.get("TWITTER_BEARER_TOKEN")
    if not bearer_token or bearer_token == "your_twitter_bearer_token_here":
        return None  # Trigger fallback
        
    print("[Social Media Ingestor] Twitter Bearer Token found! Connecting to X API...")
    
    records = []
    try:
        client = tweepy.Client(bearer_token=bearer_token)
        
        # Search query
        query = "(begal OR \"geng motor\") (bandung OR cimahi OR soreang OR baleendah) -is:retweet"
        
        # Fetch tweets
        response = client.search_recent_tweets(
            query=query, 
            max_results=20,
            tweet_fields=["created_at", "text"]
        )
        
        if response.data:
            for tweet in response.data:
                records.append({
                    "source": "social_media_x_live",
                    "text": tweet.text,
                    "timestamp": tweet.created_at.strftime("%Y-%m-%d %H:%M:%S")
                })
        print(f"[Social Media Ingestor] Successfully scraped {len(records)} live tweets from X.")
        
    except Exception as e:
        print(f"[Social Media Ingestor] ERROR connecting to X API: {e}")
        return None # Trigger fallback on error
        
    return records


def fetch_from_mock_json(data_path):
    """Fallback method: Read mock social media posts."""
    print("[Social Media Ingestor] WARNING: Twitter API keys not found or invalid.")
    print("[Social Media Ingestor] Falling back to local mock data (sample_social_media.json)...")
    
    if not os.path.exists(data_path):
        print(f"[Social Media Ingestor] ERROR: Fallback file not found: {data_path}")
        return []

    with open(data_path, "r", encoding="utf-8") as f:
        posts = json.load(f)

    records = []
    for post in posts:
        records.append({
            "source": f"social_media_{post.get('platform', 'unknown')}_mock",
            "text": post.get("text", ""),
            "timestamp": post.get("timestamp", ""),
        })

    print(f"[Social Media Ingestor] Ingested {len(records)} mock posts.")
    return records


def ingest(data_path=DEFAULT_DATA_PATH):
    """
    Main ingestion function called by the pipeline.
    Attempts live Twitter scraping, falls back to JSON if necessary.
    """
    # 1. Try Live Twitter API
    records = fetch_from_twitter_api()
    
    # 2. Fallback to mock data
    if records is None:
        records = fetch_from_mock_json(data_path)
        
    return records
