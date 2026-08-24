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
SVG_FILE = "course-status.svg"

OPEN_COLOR = "#28a745"   # green
CLOSED_COLOR = "#dc3545"  # red
UNKNOWN_COLOR = "#6c757d"  # grey, for the "unavailable" fallback case

# Card canvas sized to match the actual DAKboard block (244 x 144 px), so the
# SVG renders crisp at its native size instead of being drawn huge and then
# scaled way down by object-fit: contain.
CARD_WIDTH = 244
PADDING = 12
DOT_RADIUS = 9
HEADLINE_SIZE = 23
SUB_SIZE = 15
LINE_HEIGHT = 19
HEADLINE_GAP = 34  # vertical space between the headline and the sub-text below it


def build_svg(status_text: str, sub_text: str, color: str) -> str:
    """Renders a compact status card as SVG: colored dot + status line + wrapped
    sub line(s), sized to CARD_WIDTH. Height grows with the number of wrapped
    sub-text lines so nothing gets clipped; DAKboard's Image block (set to
    Contain fit) scales the whole thing to fill the block."""
    status_esc = escape(status_text)

    # Simple word-wrap for the sub line, since SVG <text> doesn't wrap on its own.
    # Rough average character width for a sans-serif font is ~0.55 * font-size.
    words = sub_text.split()
    lines, current = [], ""
    available_width = CARD_WIDTH - 2 * PADDING
    # 0.62 rather than the usual ~0.55 average-char-width factor, since this text
    # is often heavy with ALL CAPS (wider per character than mixed case).
    max_chars_per_line = max(10, int(available_width / (0.62 * SUB_SIZE)))
    for word in words:
        candidate = (current + " " + word).strip()
        if len(candidate) > max_chars_per_line and current:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)

    headline_y = PADDING + HEADLINE_SIZE
    sub_start_y = headline_y + HEADLINE_GAP
    height = sub_start_y + max(1, len(lines)) * LINE_HEIGHT + PADDING

    sub_tspans = "".join(
        f'<tspan x="{PADDING}" dy="{0 if i == 0 else LINE_HEIGHT}">{escape(line)}</tspan>'
        for i, line in enumerate(lines)
    )

    dot_cx = PADDING + DOT_RADIUS
    dot_cy = headline_y - HEADLINE_SIZE * 0.35
    text_x = dot_cx + DOT_RADIUS + 8

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{CARD_WIDTH}" height="{height}" viewBox="0 0 {CARD_WIDTH} {height}" preserveAspectRatio="xMidYMid meet">
  <circle cx="{dot_cx}" cy="{dot_cy}" r="{DOT_RADIUS}" fill="{color}"/>
  <text x="{text_x}" y="{headline_y}" font-family="Arial, Helvetica, sans-serif" font-size="{HEADLINE_SIZE}" font-weight="bold" fill="{color}">{status_esc}</text>
  <text x="{PADDING}" y="{sub_start_y}" font-family="Arial, Helvetica, sans-serif" font-size="{SUB_SIZE}" fill="#ffffff">{sub_tspans}</text>
</svg>
"""


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
        with open(SVG_FILE, "w", encoding="utf-8") as f:
            f.write(build_svg("Status Unknown", "Could not reach the club site", UNKNOWN_COLOR))
        sys.exit(0)  # exit 0 so the workflow still commits the fallback feed/image

    soup = BeautifulSoup(resp.text, "html.parser")
    status_span = soup.select_one(".andyShowWeatherAndCourseStatus .statusBox .updatedate")

    if status_span is None:
        feed = build_feed("Course status unavailable", "Status block not found - site markup may have changed.")
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            f.write(feed)
        with open(SVG_FILE, "w", encoding="utf-8") as f:
            f.write(build_svg("Status Unknown", "Site markup may have changed", UNKNOWN_COLOR))
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

    # SVG status card: strip the leading "Brighton & Hove Golf Course:" label
    # so the headline stays short (e.g. "Course Open"), keep the rest as the sub line.
    headline = "Course Open" if is_open else "Course Closed"
    sub_line = re.sub(r"^Brighton & Hove Golf Course:\s*", "", full_text)
    sub_line = re.sub(r"^Course (Open|Closed)\s*", "", sub_line, flags=re.IGNORECASE).strip()
    color = OPEN_COLOR if is_open else CLOSED_COLOR
    with open(SVG_FILE, "w", encoding="utf-8") as f:
        f.write(build_svg(headline, sub_line, color))


if __name__ == "__main__":
    main()
