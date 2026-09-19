#!/usr/bin/python3
"""Rank a slim plugin catalog and print overlay rows as JSON."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from catalog import in_default_pool, load_index, present_categories

GITHUB_REPO = re.compile(
    r"^https://github\.com/[A-Za-z0-9._-]+/[A-Za-z0-9._-]+(?:\.git)?/?$"
)
ADD_COMMAND = re.compile(
    r"^omarchy plugin add (https://github\.com/[A-Za-z0-9._-]+/[A-Za-z0-9._-]+(?:\.git)?/?)(?: --enable)?$"
)
KIND_ICONS = {
    "Bar widget": "󰕮",
    "Overlay": "󰘔",
    "Panel": "󰏘",
    "Service": "󰒓",
    "Bar": "󰖯",
    "Menu + Bar widget": "󰍜",
    "Service + Bar widget": "󰒓",
}
WORD_SPLIT = re.compile(r"[^a-z0-9]+")
LIMIT_DEFAULT = 120
LISTING_URL = "https://plugins.omarchy.org/plugin.html?id="


def parse_install_url(command: str, repo: str = "") -> str:
    text = str(command or "").strip()
    match = ADD_COMMAND.fullmatch(text)
    if match:
        url = match.group(1).rstrip("/")
        if not url.endswith(".git"):
            url += ".git"
        return url
    repo_url = str(repo or "").strip()
    if GITHUB_REPO.fullmatch(repo_url) and str(command or "").strip() == "":
        return ""
    return ""


def tokens(value: str) -> set[str]:
    return {part for part in WORD_SPLIT.split(value.lower()) if part}


def score_one(plugin: dict[str, Any], query: str) -> int | None:
    needle = query.strip().lower()
    if not needle:
        return 0
    name = str(plugin.get("name") or "").lower()
    plugin_id = str(plugin.get("id") or "").lower()
    short_id = plugin_id.rsplit(".", 1)[-1]
    if name == needle:
        return 1000
    if plugin_id == needle:
        return 950
    if name.startswith(needle):
        return 900
    if plugin_id.startswith(needle) or plugin_id.endswith("." + needle):
        return 850
    if short_id.startswith(needle):
        return 800
    if needle in name:
        return 700
    if needle in short_id:
        return 650
    author = str(plugin.get("author") or "").lower()
    if needle == author or needle in tokens(author):
        return 600
    tags = [str(tag).lower() for tag in (plugin.get("tags") or [])]
    if needle in tags:
        return 550
    category = str(plugin.get("category") or "").lower()
    if needle == category:
        return 500
    description = str(plugin.get("description") or "").lower()
    if re.search(r"\b" + re.escape(needle) + r"\b", description):
        return 400
    return None


def score_plugin(plugin: dict[str, Any], query: str) -> int | None:
    words = [word for word in query.strip().lower().split() if word]
    if not words:
        return 0
    if len(words) == 1:
        return score_one(plugin, words[0])
    scores = [score_one(plugin, word) for word in words]
    if any(value is None for value in scores):
        return None
    return min(int(value) for value in scores)


def kind_icon(kind: str) -> str:
    return KIND_ICONS.get(str(kind or ""), "󰐱")


def format_count(value: Any) -> str:
    try:
        number = int(value or 0)
    except (TypeError, ValueError):
        number = 0
    if number < 0:
        number = 0
    if number < 1000:
        return str(number)
    if number < 9950:
        tenths = (number + 50) // 100
        if tenths % 10 == 0:
            return f"{tenths // 10}k"
        return f"{tenths // 10}.{tenths % 10}k"
    return f"{(number + 500) // 1000}k"


def detail_text(plugin: dict[str, Any], *, installed: bool) -> str:
    parts: list[str] = []
    author = str(plugin.get("author") or "").strip()
    category = str(plugin.get("category") or "").strip()
    if author:
        parts.append(author)
    if category:
        parts.append(category)
    if str(plugin.get("status") or "") == "Manual setup":
        parts.append("manual setup")
    if installed:
        parts.append("installed")
    return " · ".join(parts)


def listing_url(plugin_id: str) -> str:
    from urllib.parse import quote

    return LISTING_URL + quote(plugin_id, safe="")


def row_for(plugin: dict[str, Any], *, installed: bool) -> dict[str, Any]:
    plugin_id = str(plugin.get("id") or "")
    install_url = parse_install_url(
        str(plugin.get("installCommand") or ""),
        str(plugin.get("repo") or ""),
    )
    can_install = bool(install_url) and not installed
    stars = int(plugin.get("stars") or 0)
    hearts = int(plugin.get("hearts") or 0)
    copies = int(plugin.get("copies") or 0)
    return {
        "pluginId": plugin_id,
        "name": str(plugin.get("name") or plugin_id),
        "detail": detail_text(plugin, installed=installed),
        "icon": kind_icon(str(plugin.get("kind") or "")),
        "repo": str(plugin.get("repo") or ""),
        "listingUrl": listing_url(plugin_id),
        "installUrl": install_url,
        "canInstall": can_install,
        "installed": installed,
        "verified": str(plugin.get("verificationStatus") or "") == "verified",
        "stars": stars,
        "hearts": hearts,
        "copies": copies,
        "starsText": format_count(stars) if stars else "",
        "heartsText": format_count(hearts) if hearts else "",
        "copiesText": format_count(copies) if copies else "",
    }


def installed_ids(raw: str | None = None) -> set[str]:
    if raw is None:
        try:
            output = subprocess.check_output(
                ["omarchy", "plugin", "list", "--json"],
                text=True,
                timeout=8,
            )
        except (OSError, subprocess.SubprocessError):
            return set()
    else:
        output = raw
    try:
        data = json.loads(output)
    except json.JSONDecodeError:
        return set()
    if not isinstance(data, list):
        return set()
    ids = set()
    for item in data:
        if isinstance(item, dict) and item.get("id"):
            ids.add(str(item["id"]))
    return ids


def matches_category(plugin: dict[str, Any], category: str) -> bool:
    wanted = str(category or "").strip()
    if not wanted:
        return True
    return str(plugin.get("category") or "") == wanted


def search_rows(
    plugins: Iterable[dict[str, Any]],
    query: str,
    installed: set[str],
    *,
    limit: int = LIMIT_DEFAULT,
    category: str = "",
) -> list[dict[str, Any]]:
    ranked: list[tuple[int, int, int, int, int, dict[str, Any]]] = []
    needle = query.strip()
    for index, plugin in enumerate(plugins):
        if not in_default_pool(plugin):
            continue
        if not matches_category(plugin, category):
            continue
        score = score_plugin(plugin, needle)
        if score is None:
            continue
        hearts = int(plugin.get("hearts") or 0)
        copies = int(plugin.get("copies") or 0)
        stars = int(plugin.get("stars") or 0)
        ranked.append((score, hearts, copies, stars, -index, plugin))
    ranked.sort(key=lambda item: (item[0], item[1], item[2], item[3], item[4]), reverse=True)
    rows = []
    for _score, _hearts, _copies, _stars, _order, plugin in ranked[: max(0, limit)]:
        rows.append(row_for(plugin, installed=str(plugin.get("id") or "") in installed))
    return rows


def main(argv: list[str]) -> int:
    query = ""
    category = ""
    index_file: Path | None = None
    installed_raw: str | None = None
    installed_csv = ""
    limit = LIMIT_DEFAULT
    list_categories = False
    args = list(argv)
    while args:
        arg = args.pop(0)
        if arg == "--query" and args:
            query = args.pop(0)
        elif arg == "--category" and args:
            category = args.pop(0)
        elif arg == "--categories":
            list_categories = True
        elif arg == "--index" and args:
            index_file = Path(args.pop(0))
        elif arg == "--installed-json" and args:
            installed_raw = Path(args.pop(0)).read_text(encoding="utf-8")
        elif arg == "--installed-ids" and args:
            installed_csv = args.pop(0)
        elif arg == "--limit" and args:
            limit = int(args.pop(0))
        elif not arg.startswith("-") and not query:
            query = arg
        else:
            print(f"unknown argument: {arg}", file=sys.stderr)
            return 2

    index = load_index(index_file)
    if index is None:
        sys.stdout.write("[]\n")
        return 0
    if list_categories:
        sys.stdout.write(json.dumps(present_categories(index.get("plugins") or []), ensure_ascii=False) + "\n")
        return 0
    if installed_csv:
        present = {item for item in installed_csv.split(",") if item}
    else:
        present = installed_ids(installed_raw)
    rows = search_rows(
        index.get("plugins") or [],
        query,
        present,
        limit=limit,
        category=category,
    )
    sys.stdout.write(json.dumps(rows, ensure_ascii=False) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
