#!/usr/bin/env python3
"""Generate a compact language card from GitHub's Linguist statistics."""

from __future__ import annotations

import argparse
from collections import Counter
import html
import json
import os
from pathlib import Path
import urllib.parse
import urllib.request


API_ROOT = "https://api.github.com"
LANGUAGE_COLORS = {
    "Astro": "#ff5a03",
    "C": "#555555",
    "C#": "#178600",
    "C++": "#f34b7d",
    "CSS": "#663399",
    "Go": "#00add8",
    "HTML": "#e34c26",
    "Java": "#b07219",
    "JavaScript": "#f1e05a",
    "Jupyter Notebook": "#da5b0b",
    "Kotlin": "#a97bff",
    "Python": "#3572a5",
    "Rust": "#dea584",
    "Shell": "#89e051",
    "TypeScript": "#3178c6",
    "Vue": "#41b883",
}
FALLBACK_COLORS = ("#6e7781", "#8250df", "#bf8700", "#1a7f37", "#cf222e")


def api_json(url: str, token: str) -> object:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "User-Agent": "Chenqiang-Zhang-profile/1.0",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def collect_languages(owner: str, token: str) -> Counter[str]:
    query = urllib.parse.urlencode(
        {"type": "owner", "sort": "updated", "direction": "desc", "per_page": 100}
    )
    repositories = api_json(f"{API_ROOT}/users/{owner}/repos?{query}", token)
    if not isinstance(repositories, list):
        raise RuntimeError("GitHub did not return a repository list")

    totals: Counter[str] = Counter()
    for repository in repositories:
        if repository.get("fork") or repository.get("archived"):
            continue
        languages = api_json(repository["languages_url"], token)
        if isinstance(languages, dict):
            totals.update({name: int(size) for name, size in languages.items()})
    if not totals:
        raise RuntimeError("No language data was returned for public repositories")
    return totals


def color_for(language: str, index: int) -> str:
    return LANGUAGE_COLORS.get(language, FALLBACK_COLORS[index % len(FALLBACK_COLORS)])


def render_svg(totals: Counter[str], theme: str) -> str:
    palette = {
        "light": {
            "background": "#ffffff",
            "border": "#d0d7de",
            "text": "#1f2328",
            "muted": "#656d76",
            "track": "#eaeef2",
        },
        "dark": {
            "background": "#0d1117",
            "border": "#30363d",
            "text": "#e6edf3",
            "muted": "#8b949e",
            "track": "#21262d",
        },
    }[theme]

    grand_total = sum(totals.values())
    ranked = totals.most_common(6)
    display_total = sum(size for _, size in ranked)
    rows: list[str] = []
    bar_segments: list[str] = []
    x_cursor = 24.0
    bar_width = 632.0

    for index, (language, size) in enumerate(ranked):
        color = color_for(language, index)
        fraction = size / display_total
        width = bar_width * fraction
        bar_segments.append(
            f'<rect x="{x_cursor:.2f}" y="58" width="{max(width, 1):.2f}" height="12" fill="{color}" />'
        )
        x_cursor += width

        column = index % 2
        row = index // 2
        x = 24 + column * 320
        y = 105 + row * 34
        percent = size / grand_total * 100
        name = html.escape(language)
        rows.append(
            f'<circle cx="{x + 6}" cy="{y - 5}" r="6" fill="{color}" />'
            f'<text x="{x + 20}" y="{y}" class="language">{name}</text>'
            f'<text x="{x + 292}" y="{y}" text-anchor="end" class="percent">{percent:.1f}%</text>'
        )

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="680" height="210" viewBox="0 0 680 210" role="img" aria-labelledby="title desc">
  <title id="title">Languages in public repositories</title>
  <desc id="desc">Top programming languages calculated from GitHub Linguist code sizes across public, non-fork repositories.</desc>
  <style>
    .heading {{ font: 600 16px ui-sans-serif, system-ui, -apple-system, Segoe UI, sans-serif; fill: {palette['text']}; }}
    .language {{ font: 500 14px ui-sans-serif, system-ui, -apple-system, Segoe UI, sans-serif; fill: {palette['text']}; }}
    .percent, .note {{ font: 12px ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; fill: {palette['muted']}; }}
  </style>
  <rect x="1" y="1" width="678" height="208" rx="12" fill="{palette['background']}" stroke="{palette['border']}" />
  <text x="24" y="35" class="heading">Public repository language mix</text>
  <rect x="24" y="58" width="632" height="12" rx="6" fill="{palette['track']}" />
  <clipPath id="bar"><rect x="24" y="58" width="632" height="12" rx="6" /></clipPath>
  <g clip-path="url(#bar)">{''.join(bar_segments)}</g>
  {''.join(rows)}
  <text x="24" y="194" class="note">GitHub Linguist · code size · public non-fork repositories</text>
</svg>
'''


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--theme", choices=("light", "dark"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    token = os.environ.get("GITHUB_TOKEN")
    owner = os.environ.get("GITHUB_REPOSITORY_OWNER", "Chenqiang-Zhang")
    if not token:
        raise RuntimeError("GITHUB_TOKEN is required")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render_svg(collect_languages(owner, token), args.theme), encoding="utf-8")


if __name__ == "__main__":
    main()
