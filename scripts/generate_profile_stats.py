#!/usr/bin/env python3
"""Generate GitHub-style overview and language cards from public profile data."""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timedelta, timezone
import html
import json
import os
from pathlib import Path
from typing import Optional
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


def api_json(url: str, token: str, payload: Optional[dict] = None) -> object:
    data = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(
        url,
        data=data,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "Chenqiang-Zhang-profile/1.0",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def public_repositories(owner: str, token: str) -> list[dict]:
    query = urllib.parse.urlencode(
        {"type": "owner", "sort": "updated", "direction": "desc", "per_page": 100}
    )
    result = api_json(f"{API_ROOT}/users/{owner}/repos?{query}", token)
    if not isinstance(result, list):
        raise RuntimeError("GitHub did not return a repository list")
    return [repository for repository in result if not repository.get("fork")]


def collect_languages(repositories: list[dict], token: str) -> Counter[str]:
    totals: Counter[str] = Counter()
    for repository in repositories:
        if repository.get("archived"):
            continue
        languages = api_json(repository["languages_url"], token)
        if isinstance(languages, dict):
            totals.update({name: int(size) for name, size in languages.items()})
    if not totals:
        raise RuntimeError("No language data was returned for public repositories")
    return totals


def collect_overview(owner: str, repositories: list[dict], token: str) -> list[tuple[str, int, str]]:
    profile = api_json(f"{API_ROOT}/users/{owner}", token)
    now = datetime.now(timezone.utc)
    since = now - timedelta(days=365)
    query = """
      query($login: String!, $from: DateTime!, $to: DateTime!) {
        user(login: $login) {
          contributionsCollection(from: $from, to: $to) {
            contributionCalendar { totalContributions }
          }
        }
      }
    """
    response = api_json(
        f"{API_ROOT}/graphql",
        token,
        {
            "query": query,
            "variables": {"login": owner, "from": since.isoformat(), "to": now.isoformat()},
        },
    )
    if not isinstance(response, dict) or response.get("errors"):
        raise RuntimeError(f"GitHub GraphQL query failed: {response.get('errors')}")
    user = response["data"]["user"]

    return [
        ("Stars", sum(int(repository["stargazers_count"]) for repository in repositories), "star"),
        ("Forks", sum(int(repository["forks_count"]) for repository in repositories), "fork"),
        (
            "Contributions (past year)",
            int(user["contributionsCollection"]["contributionCalendar"]["totalContributions"]),
            "calendar",
        ),
        ("Public repositories", int(profile["public_repos"]), "repository"),
        ("Followers", int(profile["followers"]), "people"),
        ("Following", int(profile["following"]), "branch"),
    ]


def palette(theme: str) -> dict[str, str]:
    return {
        "light": {
            "background": "#ffffff",
            "border": "#d0d7de",
            "text": "#1f2328",
            "muted": "#656d76",
            "track": "#eaeef2",
            "accent": "#0969da",
        },
        "dark": {
            "background": "#0d1117",
            "border": "#30363d",
            "text": "#e6edf3",
            "muted": "#8b949e",
            "track": "#21262d",
            "accent": "#58a6ff",
        },
    }[theme]


def icon(name: str, x: int, y: int, stroke: str) -> str:
    shapes = {
        "star": '<polygon points="12,2 15,8 22,9 17,14 18,21 12,18 6,21 7,14 2,9 9,8" />',
        "fork": '<circle cx="6" cy="5" r="2"/><circle cx="18" cy="5" r="2"/><circle cx="12" cy="19" r="2"/><path d="M6 7v3c0 3 6 2 6 6v1M18 7v3c0 3-6 2-6 6"/>',
        "calendar": '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M7 2v6M17 2v6M3 10h18M7 14h2M12 14h2M17 14h1M7 18h2M12 18h2"/>',
        "repository": '<rect x="4" y="3" width="16" height="18" rx="2"/><path d="M8 3v18M8 17h9M8 7h8"/>',
        "people": '<circle cx="9" cy="8" r="4"/><circle cx="18" cy="9" r="3"/><path d="M2 21c0-5 3-8 7-8s7 3 7 8M15 15c4 0 7 2 7 6"/>',
        "branch": '<circle cx="7" cy="5" r="2"/><circle cx="17" cy="9" r="2"/><circle cx="7" cy="19" r="2"/><path d="M7 7v10M9 10h3c3 0 5-1 5-3"/>',
    }
    return f'<g transform="translate({x} {y})" fill="none" stroke="{stroke}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">{shapes[name]}</g>'


def render_overview(metrics: list[tuple[str, int, str]], theme: str, owner: str) -> str:
    colors = palette(theme)
    rows: list[str] = []
    for index, (label, value, icon_name) in enumerate(metrics):
        y = 104 + index * 39
        rows.append(icon(icon_name, 30, y - 22, colors["muted"]))
        rows.append(f'<text x="72" y="{y}" class="label">{html.escape(label)}</text>')
        rows.append(f'<text x="620" y="{y}" text-anchor="end" class="value">{value:,}</text>')

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="680" height="360" viewBox="0 0 680 360" role="img" aria-labelledby="title desc">
  <title id="title">{html.escape(owner)} GitHub statistics</title>
  <desc id="desc">Public GitHub stars, forks, contributions, repositories, followers, and contributed repositories.</desc>
  <style>
    .heading {{ font: 650 24px ui-sans-serif, system-ui, -apple-system, Segoe UI, sans-serif; fill: {colors['accent']}; }}
    .label, .value {{ font: 17px ui-sans-serif, system-ui, -apple-system, Segoe UI, sans-serif; fill: {colors['muted']}; }}
    .value {{ font-variant-numeric: tabular-nums; }}
    .note {{ font: 11px ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; fill: {colors['muted']}; }}
  </style>
  <rect x="1" y="1" width="678" height="358" rx="12" fill="{colors['background']}" stroke="{colors['border']}" />
  <text x="32" y="52" class="heading">Chenqiang's GitHub Statistics</text>
  {''.join(rows)}
  <text x="32" y="338" class="note">Public profile data · refreshed daily</text>
</svg>
'''


def color_for(language: str, index: int) -> str:
    return LANGUAGE_COLORS.get(language, FALLBACK_COLORS[index % len(FALLBACK_COLORS)])


def render_languages(totals: Counter[str], theme: str) -> str:
    colors = palette(theme)
    grand_total = sum(totals.values())
    ranked = totals.most_common(10)
    rows: list[str] = []
    segments: list[str] = []
    x_cursor = 32.0
    bar_width = 616.0

    for index, (language, size) in enumerate(ranked):
        color = color_for(language, index)
        fraction = size / grand_total
        width = bar_width * fraction
        segments.append(
            f'<rect x="{x_cursor:.2f}" y="76" width="{max(width, 1):.2f}" height="14" fill="{color}" />'
        )
        x_cursor += width

        column = index % 2
        row = index // 2
        x = 32 + column * 310
        y = 134 + row * 39
        percent = fraction * 100
        rows.append(
            f'<circle cx="{x + 7}" cy="{y - 6}" r="7" fill="{color}" />'
            f'<text x="{x + 25}" y="{y}" class="language">{html.escape(language)}</text>'
            f'<text x="{x + 280}" y="{y}" text-anchor="end" class="percent">{percent:.2f}%</text>'
        )

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="680" height="360" viewBox="0 0 680 360" role="img" aria-labelledby="title desc">
  <title id="title">Languages used by file size</title>
  <desc id="desc">Top languages calculated from GitHub Linguist code sizes across public, non-fork repositories.</desc>
  <style>
    .heading {{ font: 650 24px ui-sans-serif, system-ui, -apple-system, Segoe UI, sans-serif; fill: {colors['text']}; }}
    .language {{ font: 600 16px ui-sans-serif, system-ui, -apple-system, Segoe UI, sans-serif; fill: {colors['text']}; }}
    .percent {{ font: 14px ui-sans-serif, system-ui, -apple-system, Segoe UI, sans-serif; fill: {colors['muted']}; font-variant-numeric: tabular-nums; }}
    .note {{ font: 11px ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; fill: {colors['muted']}; }}
  </style>
  <rect x="1" y="1" width="678" height="358" rx="12" fill="{colors['background']}" stroke="{colors['border']}" />
  <text x="32" y="52" class="heading">Languages Used (By File Size)</text>
  <rect x="32" y="76" width="616" height="14" rx="7" fill="{colors['track']}" />
  <clipPath id="bar"><rect x="32" y="76" width="616" height="14" rx="7" /></clipPath>
  <g clip-path="url(#bar)">{''.join(segments)}</g>
  {''.join(rows)}
  <text x="32" y="338" class="note">GitHub Linguist · public non-fork repositories</text>
</svg>
'''


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--theme", choices=("light", "dark"), required=True)
    parser.add_argument("--overview-output", type=Path, required=True)
    parser.add_argument("--languages-output", type=Path, required=True)
    args = parser.parse_args()

    token = os.environ.get("GITHUB_TOKEN")
    owner = os.environ.get("GITHUB_REPOSITORY_OWNER", "Chenqiang-Zhang")
    if not token:
        raise RuntimeError("GITHUB_TOKEN is required")

    repositories = public_repositories(owner, token)
    metrics = collect_overview(owner, repositories, token)
    languages = collect_languages(repositories, token)
    args.overview_output.parent.mkdir(parents=True, exist_ok=True)
    args.languages_output.parent.mkdir(parents=True, exist_ok=True)
    args.overview_output.write_text(render_overview(metrics, args.theme, owner), encoding="utf-8")
    args.languages_output.write_text(render_languages(languages, args.theme), encoding="utf-8")


if __name__ == "__main__":
    main()
