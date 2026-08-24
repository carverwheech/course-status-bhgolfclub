#!/usr/bin/env python3
"""Scrapes the club's IntelligentGolf 'plasma' diary/news board and
republishes it as an RSS feed (club-diary.xml) for DAKboard's RSS block.

The source page (brightongolf.co.uk/live4) blocks being shown in an iframe
(X-Frame-Options), so it can't be embedded directly - this scrapes the
server-rendered HTML instead, same trick as the course-status scraper."""

import re
import sys
from datetime import datetime, timezone
from email.utils import format_datetime
from xml.sax.saxutils import escape

import requests
from bs4 import BeautifulSoup

SOURCE_URL = "https://www.brightongolf.co.uk/live4?page=0"
OUTPUT_FILE = "club-diary.xml"


def clean(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def collect_items(soup: BeautifulSoup, container_id: str, label: str):
    """Pulls (title, description, section-label) tuples from a panel-column."""
    items = []
    container = soup.find(id=container_id)
    if container is None:
        return items
    for panel_item in container.select(".panel-content .panel-item"):
        date_time = clean(panel_item.select_one(".date-time").get_text()) if panel_item.select_one(".date-time") else ""
        h3 = panel_item.find("h3")
        title = clean(h3.get_text()) if h3 else ""
        if not title:
            continue
        summary_el = panel_item.find("div", class_="summary")
        summary = clean(summary_el.get_text()) if summary_el else ""
        description = f"{label}: {date_time}" + (f" \u2014 {summary}" if summary else "")
        items.append((title, description))
    return items


def build_feed(items) -> str:
    pub_date = format_datetime(datetime.now(timezone.utc))
    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<rss version="2.0"><channel>',
        "<title>Brighton &amp; Hove Golf Club - Diary &amp; News</title>",
        f"<link>{escape(SOURCE_URL)}</link>",
        "<description>Upcoming events and club news</description>",
    ]
    if not items:
        parts.append("<item><title>No upcoming events found</title>"
                      "<description>Check the club website directly.</description></item>")
    for title, description in items:
        parts.append("<item>")
        parts.append(f"<title>{escape(title)}</title>")
        parts.append(f"<description>{escape(description)}</description>")
        parts.append(f"<pubDate>{pub_date}</pubDate>")
        parts.append("</item>")
    parts.append("</channel></rss>")
    return "\n".join(parts) + "\n"


def main():
    try:
        resp = requests.get(SOURCE_URL, timeout=10, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        })
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        items = []
        items += collect_items(soup, "diary-today", "Today")
        items += collect_items(soup, "diary-thisweek", "This Week")
        items += collect_items(soup, "diary-nextweek", "Next Week")

        if not items:
            # Diagnostic fallback: report what we actually got back, so we can
            # tell "site blocked the request" apart from "genuinely no events".
            found_ids = {
                cid: (soup.find(id=cid) is not None)
                for cid in ["diary-today", "diary-thisweek", "diary-nextweek", "diary-container"]
            }
            debug = (
                f"HTTP {resp.status_code}, {len(resp.text)} bytes. "
                f"Containers found: {found_ids}. "
                f"Title tag: {soup.title.get_text(strip=True) if soup.title else 'none'}."
            )
            feed = build_feed([("No upcoming events found", debug)])
        else:
            feed = build_feed(items)
    except Exception as exc:
        feed = build_feed([("Diary unavailable", f"Could not reach site: {exc}")])

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(feed)


if __name__ == "__main__":
    main()
