#!/usr/bin/env python3
"""Refresh the latest-posts block in the profile README from the blog RSS feed."""

from __future__ import annotations

from email.utils import parsedate_to_datetime
from pathlib import Path
import re
import urllib.request
import xml.etree.ElementTree as ET


FEED_URL = "https://chenqiang-zhang.github.io/rss.xml"
START = "<!-- BLOG-POST-LIST:START -->"
END = "<!-- BLOG-POST-LIST:END -->"
ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"


def markdown_text(value: str) -> str:
    """Escape the characters that can break a Markdown link label."""
    return value.replace("\\", "\\\\").replace("[", "\\[").replace("]", "\\]")


def fetch_posts(limit: int = 3) -> list[str]:
    request = urllib.request.Request(
        FEED_URL,
        headers={"User-Agent": "Chenqiang-Zhang-profile/1.0 (+GitHub Actions)"},
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        root = ET.fromstring(response.read())

    lines: list[str] = []
    for item in root.findall("./channel/item")[:limit]:
        title = (item.findtext("title") or "Untitled").strip()
        link = (item.findtext("link") or "").strip()
        published = (item.findtext("pubDate") or "").strip()
        if not link:
            continue
        date = parsedate_to_datetime(published).date().isoformat() if published else ""
        suffix = f" — {date}" if date else ""
        lines.append(f"- [{markdown_text(title)}]({link}){suffix}")

    if not lines:
        raise RuntimeError("The RSS feed did not contain any usable posts")
    return lines


def main() -> None:
    content = README.read_text(encoding="utf-8")
    if content.count(START) != 1 or content.count(END) != 1:
        raise RuntimeError("README must contain exactly one latest-posts marker pair")

    block = START + "\n" + "\n".join(fetch_posts()) + "\n" + END
    updated = re.sub(
        re.escape(START) + r".*?" + re.escape(END),
        block,
        content,
        flags=re.DOTALL,
    )
    README.write_text(updated, encoding="utf-8")


if __name__ == "__main__":
    main()
