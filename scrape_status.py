#!/usr/bin/env python3
"""Scrapes the course-status widget from the club homepage and writes it
out as a small RSS feed (course-status.xml) for DAKboard to consume."""

import re
import sys
from datetime import datetime, timezone
from email.utils import format_datetime
from xml.sax.saxutils import escape

import requests
from bs4 import BeautifulSoup

SOURCE_URL = "https://www.brightongolf.co.uk/"
OUTPUT_FILE = "course-status.xml"


def build_feed(title: str, description: str) -> str:
    pub_date = format_datetime(datetime.now(timezone.utc))
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
<title>Brighton &amp; Hove Golf Club - Course Status</title>
<link>{escape(SOURCE_URL)}</link>
<description>Live course status</description>
<item>
<title>{escape(title)}</title>
<description>{escape(description)}</description>
<pubDate>{pub_date}</pubDate>
</item>
</channel></rss>
"""


def main():
    try:
        resp = requests.get(SOURCE_URL, timeout=10, headers={"User-Agent": "BHGC-Kiosk/1.0"})
        resp.raise_for_status()
    except Exception as exc:
        feed = build_feed("Course status unavailable", f"Could not reach site: {exc}")
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            f.write(feed)
        sys.exit(0)  # exit 0 so the workflow still commits the fallback feed

    soup = BeautifulSoup(resp.text, "html.parser")
    status_span = soup.select_one(".andyShowWeatherAndCourseStatus .statusBox .updatedate")

    if status_span is None:
        feed = build_feed("Course status unavailable", "Status block not found - site markup may have changed.")
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            f.write(feed)
        sys.exit(0)

    updated = status_span.get("data-original-title", "").strip()

    dot = status_span.find("span")
    dot_color = dot.get("style", "") if dot else ""
    is_open = "28a745" in dot_color  # green dot = open

    full_text = status_span.get_text(separator=" ", strip=True)
    full_text = re.sub(r"^\W+\s*", "", full_text)  # strip leading bullet glyph
    full_text = re.sub(r"\s+", " ", full_text).strip()

    title = "\u25cf Course Open" if is_open else "\u25cf Course Status"
    description = full_text + (f" \u2014 {updated}" if updated else "")

    feed = build_feed(title, description)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(feed)


if __name__ == "__main__":
    main()
