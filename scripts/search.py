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
from urllib.request import Request, urlopen

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import install as install_mod
from catalog import USER_AGENT, approved_commit, in_default_pool, load_index, parse_iso, present_categories, state_dir

GITHUB_REPO = re.compile(
    r"^https://github\.com/[A-Za-z0-9._-]+/[A-Za-z0-9._-]+(?:\.git)?/?$"
)
ADD_COMMAND = re.compile(
    r"^omarchy plugin add (https://github\.com/[A-Za-z0-9._-]+/[A-Za-z0-9._-]+(?:\.git)?/?)(?: --enable)?$"
)
PREVIEW_PATH = re.compile(r"[A-Za-z0-9._/-]+")
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
PREVIEW_ORIGIN = "https://plugins.omarchy.org/"
# Below description-word (400) so a one-edit miss never outranks a real hit.
FUZZY_SCORE = 100
FUZZY_MIN = 4
MODES = ("popular", "new", "installed", "updates")
HEAD_TIMEOUT = 5


def github_git_url(url: str) -> str:
    text = str(url or "").strip().rstrip("/")
    if not GITHUB_REPO.fullmatch(text):
        return ""
    if not text.endswith(".git"):
        text += ".git"
    return text


def parse_install_url(command: str, repo: str = "") -> str:
    text = str(command or "").strip()
    match = ADD_COMMAND.fullmatch(text)
    if match:
        url = match.group(1).rstrip("/")
        if not url.endswith(".git"):
            url += ".git"
        return url
    return github_git_url(repo)


def cache_preview(url: str) -> str:
    text = str(url or "").strip()
    if not text.startswith(PREVIEW_ORIGIN):
        return ""
    relative = text[len(PREVIEW_ORIGIN):]
    if preview_url(relative) != text:
        return ""
    folder = state_dir() / "previews"
    folder.mkdir(parents=True, exist_ok=True)
    dest = folder / relative.replace("/", "_")
    if dest.is_file() and dest.stat().st_size > 32:
        return str(dest)
    request = Request(text, headers={"User-Agent": USER_AGENT})
    try:
        with urlopen(request, timeout=20) as response:
            if not str(response.geturl()).startswith(PREVIEW_ORIGIN):
                return ""
            data = response.read(8_000_000)
    except (OSError, ValueError):
        return ""
    if not data:
        return ""
    partial = dest.with_name(dest.name + ".part")
    partial.write_bytes(data)
    partial.replace(dest)
    return str(dest)


def preview_url(path: str) -> str:
    text = str(path or "").strip()
    if not text or "://" in text or "\\" in text or text.startswith("/"):
        return ""
    parts = text.split("/")
    if not parts or any(part in ("", ".", "..") for part in parts):
        return ""
    if not PREVIEW_PATH.fullmatch(text):
        return ""
    return PREVIEW_ORIGIN + text


def tokens(value: str) -> set[str]:
    return {part for part in WORD_SPLIT.split(value.lower()) if part}


def within_one_edit(left: str, right: str) -> bool:
    if left == right:
        return True
    if abs(len(left) - len(right)) > 1:
        return False
    if len(left) > len(right):
        left, right = right, left
    if len(left) == len(right):
        return sum(a != b for a, b in zip(left, right)) == 1
    skipped = False
    index = 0
    for char in right:
        if index < len(left) and left[index] == char:
            index += 1
        elif skipped:
            return False
        else:
            skipped = True
    return index == len(left)


def fuzzy_hit(plugin: dict[str, Any], needle: str) -> bool:
    if len(needle) < FUZZY_MIN:
        return False
    plugin_id = str(plugin.get("id") or "").lower()
    short_id = plugin_id.rsplit(".", 1)[-1]
    candidates = set(tokens(str(plugin.get("name") or "")))
    if short_id:
        candidates.add(short_id)
    return any(within_one_edit(needle, candidate) for candidate in candidates)


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
    if fuzzy_hit(plugin, needle):
        return FUZZY_SCORE
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


def detail_text(plugin: dict[str, Any], *, meta: str, enabled: bool | None) -> str:
    if meta == "installed":
        state = "enabled" if enabled else "disabled"
        return str(plugin.get("id") or "") + " · " + state
    parts: list[str] = []
    author = str(plugin.get("author") or "").strip()
    category = str(plugin.get("category") or "").strip()
    if author:
        parts.append(author)
    if category:
        parts.append(category)
    return " · ".join(parts)


def description_text(plugin: dict[str, Any]) -> str:
    return " ".join(str(plugin.get("description") or "").split())


def listing_url(plugin_id: str) -> str:
    from urllib.parse import quote

    return LISTING_URL + quote(plugin_id, safe="")


def row_for(
    plugin: dict[str, Any],
    *,
    installed: bool,
    head: str | None = None,
    enabled: bool | None = None,
    meta: str = "catalog",
    first_party: bool = False,
) -> dict[str, Any]:
    plugin_id = str(plugin.get("id") or "")
    status = str(plugin.get("status") or "")
    builtin = status == "Built in" or first_party
    install_url = ""
    install_commit = ""
    if not builtin:
        install_commit = approved_commit(plugin.get("listingValidatedCommit"))
        if install_commit:
            install_url = parse_install_url(
                str(plugin.get("installCommand") or ""),
                str(plugin.get("repo") or ""),
            )
    # None means git was not read. "" means the checkout could not be pinned.
    checked = None if head is None else approved_commit(head)
    behind = bool(
        installed
        and not builtin
        and install_commit
        and checked
        and checked != install_commit
        and in_default_pool(plugin)
    )
    can_remove = bool(installed and not builtin)
    if builtin:
        enter_action = "builtin"
    elif behind:
        enter_action = "update"
    elif can_remove:
        enter_action = "uninstall"
    elif install_url and install_commit:
        enter_action = "install"
    else:
        enter_action = ""
    can_install = enter_action == "install"
    can_update = enter_action == "update"
    if behind:
        status_label = "Update"
    elif installed:
        status_label = "Installed"
    elif status == "Manual setup":
        status_label = "Manual setup"
    else:
        status_label = ""
    actions = {
        "install": "Installs the verified snapshot",
        "update": "Updates to the verified snapshot",
        "uninstall": "Uninstalls this plugin",
        "builtin": "Built in",
        "": "",
    }
    hints: list[str] = []
    if enter_action == "install":
        hints.append("Enter install")
    elif enter_action == "update":
        hints.append("Enter update")
    elif enter_action == "uninstall":
        hints.append("Enter uninstall")
    stars = int(plugin.get("stars") or 0)
    hearts = int(plugin.get("hearts") or 0)
    copies = int(plugin.get("copies") or 0)
    return {
        "pluginId": plugin_id,
        "name": str(plugin.get("name") or plugin_id),
        "detail": detail_text(plugin, meta=meta, enabled=enabled),
        "description": description_text(plugin),
        "version": str(plugin.get("version") or "").strip(),
        "previewUrl": preview_url(str(plugin.get("previewImage") or "")),
        "manualSetup": status == "Manual setup",
        "statusLabel": status_label,
        "actionText": actions[enter_action],
        "hint": " · ".join(hints),
        "enterAction": enter_action,
        "icon": kind_icon(str(plugin.get("kind") or "")),
        "repo": str(plugin.get("repo") or ""),
        "listingUrl": listing_url(plugin_id),
        "installUrl": install_url,
        "installCommit": install_commit,
        "canInstall": can_install,
        "canUpdate": can_update,
        "canRemove": can_remove,
        "installed": installed,
        "verified": str(plugin.get("verificationStatus") or "") == "verified",
        "stars": stars,
        "hearts": hearts,
        "copies": copies,
        "starsText": format_count(stars) if stars else "",
        "heartsText": format_count(hearts) if hearts else "",
        "copiesText": format_count(copies) if copies else "",
    }


def parse_installed(output: str) -> list[dict[str, Any]]:
    try:
        data = json.loads(output)
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    rows = []
    for item in data:
        if not isinstance(item, dict) or not item.get("id"):
            continue
        plugin_id = str(item["id"])
        rows.append(
            {
                "id": plugin_id,
                "name": str(item.get("name") or plugin_id),
                "enabled": bool(item.get("enabled")),
                "firstParty": bool(item.get("firstParty")),
            }
        )
    return rows


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
    return {row["id"] for row in parse_installed(output)}


def load_installed(raw: str | None = None) -> list[dict[str, Any]]:
    if raw is None:
        try:
            output = subprocess.check_output(
                ["omarchy", "plugin", "list", "--json"],
                text=True,
                timeout=8,
            )
        except (OSError, subprocess.SubprocessError):
            return []
    else:
        output = raw
    return parse_installed(output)


def collect_heads(
    records: list[dict[str, Any]],
    plugins: Iterable[dict[str, Any]],
    root: Path | None = None,
) -> dict[str, str]:
    by_id = {str(plugin.get("id") or ""): plugin for plugin in plugins if isinstance(plugin, dict)}
    plugin_root = root or Path(os.environ.get("SEARCH_PLUGIN_ROOT") or install_mod.PLUGINS)
    folders = install_mod.plugin_dirs(plugin_root)
    origins: dict[str, Path] = {}
    for folder in sorted(folders):
        origin = install_mod.origin_url(folder)
        if origin and origin not in origins:
            origins[origin] = folder
    heads: dict[str, str] = {}
    for record in records:
        if record.get("firstParty"):
            continue
        plugin = by_id.get(str(record.get("id") or ""))
        if not plugin:
            continue
        url = parse_install_url(
            str(plugin.get("installCommand") or ""),
            str(plugin.get("repo") or ""),
        )
        folder = origins.get(install_mod.normalize_git_url(url))
        if folder is None:
            continue
        try:
            head = install_mod.git(folder, "rev-parse", "HEAD", capture=True, timeout=HEAD_TIMEOUT)
        except (OSError, subprocess.SubprocessError):
            continue
        sha = approved_commit(head)
        if sha:
            heads[str(record["id"])] = sha
    return heads


def matches_category(plugin: dict[str, Any], category: str) -> bool:
    wanted = str(category or "").strip()
    if not wanted:
        return True
    return str(plugin.get("category") or "") == wanted


def records_from_ids(installed: set[str]) -> list[dict[str, Any]]:
    return [
        {"id": plugin_id, "name": plugin_id, "enabled": True, "firstParty": False}
        for plugin_id in sorted(installed)
    ]


def catalog_rows(
    plugins: Iterable[dict[str, Any]],
    query: str,
    installed: set[str],
    *,
    limit: int,
    category: str,
    mode: str,
    heads: dict[str, str] | None,
) -> list[dict[str, Any]]:
    ranked: list[tuple[Any, ...]] = []
    needle = query.strip()
    for index, plugin in enumerate(plugins):
        if not isinstance(plugin, dict) or not in_default_pool(plugin):
            continue
        if not matches_category(plugin, category):
            continue
        score = score_plugin(plugin, needle)
        if score is None:
            continue
        hearts = int(plugin.get("hearts") or 0)
        copies = int(plugin.get("copies") or 0)
        stars = int(plugin.get("stars") or 0)
        listed = parse_iso(str(plugin.get("listedAt") or "")) or 0
        plugin_id = str(plugin.get("id") or "")
        head = None if heads is None else heads.get(plugin_id, "")
        row = row_for(
            plugin,
            installed=plugin_id in installed,
            head=head,
            first_party=str(plugin.get("status") or "") == "Built in",
        )
        if mode == "new":
            ranked.append((listed, hearts, copies, stars, -index, score, row))
        else:
            ranked.append((score, hearts, copies, stars, -index, listed, row))
    ranked.sort(reverse=True)
    cap = max(0, limit)
    return [item[-1] for item in ranked[:cap]]


def local_rows(
    plugins: Iterable[dict[str, Any]],
    query: str,
    records: list[dict[str, Any]],
    *,
    limit: int | None,
    category: str,
    mode: str,
    heads: dict[str, str] | None,
) -> list[dict[str, Any]]:
    by_id = {
        str(plugin.get("id") or ""): plugin
        for plugin in plugins
        if isinstance(plugin, dict) and plugin.get("id")
    }
    needle = query.strip()
    ranked: list[tuple[int, str, str, dict[str, Any]]] = []
    for record in records:
        if record.get("firstParty"):
            continue
        plugin_id = str(record.get("id") or "")
        source = by_id.get(plugin_id)
        if source is not None and str(source.get("status") or "") == "Built in":
            continue
        if source is None:
            plugin = {
                "id": plugin_id,
                "name": str(record.get("name") or plugin_id),
                "description": "",
                "author": "",
                "category": "",
                "tags": [],
                "status": "",
                "verificationStatus": "",
                "repo": "",
                "installCommand": "",
            }
        else:
            plugin = source
        if not matches_category(plugin, category):
            continue
        score = score_plugin(plugin, needle)
        if score is None:
            continue
        head = None if heads is None else heads.get(plugin_id, "")
        row = row_for(
            plugin,
            installed=True,
            head=head,
            enabled=bool(record.get("enabled")),
            meta="installed",
            first_party=False,
        )
        if mode == "updates" and row["enterAction"] != "update":
            continue
        if source is None:
            row["name"] = str(record.get("name") or plugin_id)
        ranked.append((-int(score or 0), row["name"].lower(), plugin_id, row))
    ranked.sort()
    rows = [item[-1] for item in ranked]
    if limit is None:
        return rows
    return rows[: max(0, limit)]


def search_rows(
    plugins: Iterable[dict[str, Any]],
    query: str,
    installed: set[str],
    *,
    limit: int | None = None,
    category: str = "",
    mode: str = "popular",
    heads: dict[str, str] | None = None,
    installed_records: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    if mode not in MODES:
        raise ValueError(f"unknown mode: {mode}")
    plugin_list = list(plugins)
    if mode in ("installed", "updates"):
        records = installed_records if installed_records is not None else records_from_ids(installed)
        return local_rows(
            plugin_list,
            query,
            records,
            limit=limit,
            category=category,
            mode=mode,
            heads=heads,
        )
    cap = LIMIT_DEFAULT if limit is None else limit
    return catalog_rows(
        plugin_list,
        query,
        installed,
        limit=cap,
        category=category,
        mode=mode,
        heads=heads,
    )


def main(argv: list[str]) -> int:
    query = ""
    category = ""
    mode = "popular"
    index_file: Path | None = None
    installed_raw: str | None = None
    installed_csv: str | None = None
    limit: int | None = None
    limit_set = False
    list_categories = False
    preview_to_cache = ""
    args = list(argv)
    while args:
        arg = args.pop(0)
        if arg == "--query" and args:
            query = args.pop(0)
        elif arg == "--category" and args:
            category = args.pop(0)
        elif arg == "--mode" and args:
            mode = args.pop(0)
        elif arg == "--categories":
            list_categories = True
        elif arg == "--cache-preview" and args:
            preview_to_cache = args.pop(0)
        elif arg == "--index" and args:
            index_file = Path(args.pop(0))
        elif arg == "--installed-json" and args:
            installed_raw = Path(args.pop(0)).read_text(encoding="utf-8")
        elif arg == "--installed-ids" and args:
            installed_csv = args.pop(0)
        elif arg == "--limit" and args:
            limit = int(args.pop(0))
            limit_set = True
        elif not arg.startswith("-") and not query:
            query = arg
        else:
            print(f"unknown argument: {arg}", file=sys.stderr)
            return 2
    if mode not in MODES:
        print(f"unknown mode: {mode}", file=sys.stderr)
        return 2
    if preview_to_cache:
        sys.stdout.write(cache_preview(preview_to_cache) + "\n")
        return 0

    index = load_index(index_file)
    if index is None:
        sys.stdout.write("[]\n" if not list_categories else "[]\n")
        return 0
    plugins = index.get("plugins") or []
    if list_categories:
        sys.stdout.write(json.dumps(present_categories(plugins), ensure_ascii=False) + "\n")
        return 0
    if installed_csv is not None:
        present_ids = {item for item in installed_csv.split(",") if item}
        records = records_from_ids(present_ids)
        heads = None
    else:
        records = load_installed(installed_raw)
        present_ids = {row["id"] for row in records}
        heads = collect_heads(records, plugins)
    rows = search_rows(
        plugins,
        query,
        present_ids,
        limit=limit if limit_set else None,
        category=category,
        mode=mode,
        heads=heads,
        installed_records=records,
    )
    sys.stdout.write(json.dumps(rows, ensure_ascii=False) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
