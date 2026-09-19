#!/usr/bin/python3
"""Fetch and slim the Omarchy plugin marketplace catalog."""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

CATALOG_URL = "https://plugins.omarchy.org/catalog.json"
STATS_URL = "https://api.omarchyplugins.com/v1/stats"
TTL_SECONDS = 6 * 60 * 60
STATS_TTL_SECONDS = 30 * 60
FETCH_TIMEOUT = 30
INDEX_MAX_BYTES = 16 * 1024 * 1024
USER_AGENT = "oliverlukschander.super-plugin-search/0.1.1"
DEFAULT_STATUSES = frozenset({"Available", "Built in", "Manual setup"})
MAX_COUNT = 9_007_199_254_740_991
OFFICIAL_CATEGORIES = (
    "Widgets",
    "Productivity",
    "System",
    "Hardware",
    "Desktop",
    "Appearance",
    "Developer Tools",
    "Kids",
    "Other",
)


def state_dir() -> Path:
    root = os.environ.get("XDG_STATE_HOME") or str(Path.home() / ".local" / "state")
    return Path(root) / "omarchy" / "super-plugin-search"


def index_path() -> Path:
    override = os.environ.get("SEARCH_PLUGIN_INDEX")
    if override:
        return Path(override)
    return state_dir() / "index.json"


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso(value: str) -> float | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        return datetime.fromisoformat(text).timestamp()
    except ValueError:
        return None


def slim_plugin(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    plugin_id = str(raw.get("id") or "").strip()
    if not plugin_id:
        return None
    tags = raw.get("tags")
    if not isinstance(tags, list):
        tags = []
    return {
        "id": plugin_id,
        "name": str(raw.get("name") or plugin_id),
        "description": str(raw.get("description") or ""),
        "author": str(raw.get("author") or ""),
        "category": str(raw.get("category") or ""),
        "tags": [str(tag) for tag in tags if tag is not None and str(tag).strip()],
        "kind": str(raw.get("kind") or ""),
        "repo": str(raw.get("repo") or ""),
        "installCommand": str(raw.get("installCommand") or ""),
        "installAvailable": bool(raw.get("installAvailable")),
        "verificationStatus": str(raw.get("verificationStatus") or ""),
        "stars": int(raw.get("stars") or 0),
        "hearts": as_count(raw.get("hearts")),
        "copies": as_count(raw.get("copies")),
        "views": as_count(raw.get("views")),
        "status": str(raw.get("status") or ""),
    }


def as_count(value: Any) -> int:
    if isinstance(value, bool) or value is None:
        return 0
    try:
        number = int(value)
    except (TypeError, ValueError):
        return 0
    if number < 0 or number > MAX_COUNT:
        return 0
    return number


def parse_stats(data: Any) -> dict[str, dict[str, int]]:
    if not isinstance(data, dict) or data.get("schemaVersion") != 1:
        raise ValueError("stats schema is not version 1")
    plugins = data.get("plugins")
    if not isinstance(plugins, dict):
        raise ValueError("stats plugins is not an object")
    out: dict[str, dict[str, int]] = {}
    for plugin_id, metrics in plugins.items():
        if not plugin_id or not isinstance(metrics, dict):
            continue
        out[str(plugin_id)] = {
            "hearts": as_count(metrics.get("hearts")),
            "copies": as_count(metrics.get("copies")),
            "views": as_count(metrics.get("views")),
        }
    return out


def apply_stats(index: dict[str, Any], stats_map: dict[str, dict[str, int]]) -> dict[str, Any]:
    plugins = []
    for plugin in index.get("plugins") or []:
        if not isinstance(plugin, dict):
            continue
        row = dict(plugin)
        metrics = stats_map.get(str(row.get("id") or "")) or {}
        row["hearts"] = as_count(metrics.get("hearts"))
        row["copies"] = as_count(metrics.get("copies"))
        row["views"] = as_count(metrics.get("views"))
        plugins.append(row)
    next_index = dict(index)
    next_index["plugins"] = plugins
    return next_index


def in_default_pool(plugin: dict[str, Any]) -> bool:
    # Manual setup listings are real marketplace plugins that need an extra
    # step after clone. Unverified community listings stay out: this overlay
    # is a one-Enter installer, not a gallery of every HEAD on GitHub.
    if str(plugin.get("status") or "") not in DEFAULT_STATUSES:
        return False
    if str(plugin.get("status") or "") == "Built in":
        return True
    return str(plugin.get("verificationStatus") or "") == "verified"


def present_categories(plugins: list[dict[str, Any]]) -> list[str]:
    seen: set[str] = set()
    for plugin in plugins:
        if in_default_pool(plugin):
            seen.add(str(plugin.get("category") or ""))
    return [name for name in OFFICIAL_CATEGORIES if name in seen]


def slim_catalog(data: Any, *, fetched_at: str, etag: str = "") -> dict[str, Any]:
    if not isinstance(data, dict):
        raise ValueError("catalog is not an object")
    plugins_raw = data.get("plugins")
    if not isinstance(plugins_raw, list):
        raise ValueError("catalog plugins is not a list")
    plugins = []
    for item in plugins_raw:
        slim = slim_plugin(item)
        if slim:
            plugins.append(slim)
    return {
        "generatedAt": str(data.get("generatedAt") or ""),
        "fetchedAt": fetched_at,
        "etag": etag,
        "statsFetchedAt": "",
        "statsEtag": "",
        "source": CATALOG_URL,
        "plugins": plugins,
    }


def load_index(path: Path | None = None) -> dict[str, Any] | None:
    target = path or index_path()
    try:
        raw = target.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    except OSError:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict) or not isinstance(data.get("plugins"), list):
        return None
    return data


def index_is_fresh(index: dict[str, Any], *, now: float | None = None, ttl: int = TTL_SECONDS) -> bool:
    stamp = parse_iso(str(index.get("fetchedAt") or ""))
    if stamp is None:
        return False
    current = time.time() if now is None else now
    return (current - stamp) < ttl


def stats_are_fresh(index: dict[str, Any], *, now: float | None = None, ttl: int = STATS_TTL_SECONDS) -> bool:
    stamp = parse_iso(str(index.get("statsFetchedAt") or ""))
    if stamp is None:
        return False
    current = time.time() if now is None else now
    return (current - stamp) < ttl


def write_index(path: Path, index: dict[str, Any]) -> None:
    payload = json.dumps(index, ensure_ascii=False, separators=(",", ":"))
    data = (payload + "\n").encode()
    if len(data) > INDEX_MAX_BYTES:
        raise ValueError(f"index too large ({len(data)} bytes)")
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.parent / f".{path.name}.{os.getpid()}.tmp"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        written = 0
        while written < len(data):
            written += os.write(fd, data[written:])
        os.fsync(fd)
    finally:
        os.close(fd)
    os.replace(tmp, path)


Fetcher = Callable[[str, str], tuple[int, bytes, str]]


def default_fetcher(url: str, etag: str) -> tuple[int, bytes, str]:
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    if etag:
        headers["If-None-Match"] = etag
    request = Request(url, headers=headers, method="GET")
    try:
        with urlopen(request, timeout=FETCH_TIMEOUT) as response:
            body = response.read(INDEX_MAX_BYTES + 1)
            if len(body) > INDEX_MAX_BYTES:
                raise ValueError("catalog response too large")
            return int(response.status), body, str(response.headers.get("ETag") or "")
    except HTTPError as exc:
        body = exc.read(1024) if exc.fp is not None else b""
        return int(exc.code), body, str(exc.headers.get("ETag") or "")


def refresh_stats(
    index: dict[str, Any],
    *,
    force: bool = False,
    path: Path | None = None,
    fetcher: Fetcher = default_fetcher,
) -> dict[str, Any]:
    target = path or index_path()
    if not force and stats_are_fresh(index):
        return {"ok": True, "refreshed": False, "error": ""}
    etag = str(index.get("statsEtag") or "")
    try:
        status, body, new_etag = fetcher(STATS_URL, etag)
    except (URLError, TimeoutError, ValueError, OSError) as exc:
        return {"ok": False, "refreshed": False, "error": str(exc)}
    if status == 304:
        index["statsFetchedAt"] = now_iso()
        if new_etag:
            index["statsEtag"] = new_etag
        write_index(target, index)
        return {"ok": True, "refreshed": True, "error": ""}
    if status != 200:
        return {"ok": False, "refreshed": False, "error": f"HTTP {status}"}
    try:
        parsed = json.loads(body.decode())
        merged = apply_stats(index, parse_stats(parsed))
        merged["statsFetchedAt"] = now_iso()
        merged["statsEtag"] = new_etag or etag
        write_index(target, merged)
        index.clear()
        index.update(merged)
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError, OSError) as exc:
        return {"ok": False, "refreshed": False, "error": str(exc)}
    return {"ok": True, "refreshed": True, "error": ""}


def refresh(
    *,
    force: bool = False,
    path: Path | None = None,
    fetcher: Fetcher = default_fetcher,
    url: str = CATALOG_URL,
) -> dict[str, Any]:
    target = path or index_path()
    current = load_index(target)
    catalog_error = ""
    refreshed = False

    if current is None or force or not index_is_fresh(current):
        etag = str((current or {}).get("etag") or "")
        try:
            status, body, new_etag = fetcher(url, etag)
        except (URLError, TimeoutError, ValueError, OSError) as exc:
            catalog_error = str(exc)
            status, body, new_etag = 0, b"", ""

        if status == 304 and current is not None:
            current = dict(current)
            current["fetchedAt"] = now_iso()
            if new_etag:
                current["etag"] = new_etag
            write_index(target, current)
            refreshed = True
        elif status == 200:
            try:
                parsed = json.loads(body.decode())
                current = slim_catalog(parsed, fetched_at=now_iso(), etag=new_etag or etag)
                write_index(target, current)
                refreshed = True
                force = True
            except (ValueError, UnicodeDecodeError, json.JSONDecodeError, OSError) as exc:
                catalog_error = str(exc)
        elif not catalog_error and status not in (0, 304):
            catalog_error = f"HTTP {status}"

    if current is None:
        return {
            "ok": False,
            "refreshed": False,
            "count": 0,
            "fetchedAt": "",
            "error": catalog_error or "no catalog",
        }

    stats = refresh_stats(current, force=force, path=target, fetcher=fetcher)
    latest = load_index(target) or current
    error = catalog_error
    if not error and not stats["ok"]:
        error = stats["error"]
    return {
        "ok": True,
        "refreshed": refreshed or bool(stats.get("refreshed")),
        "count": len(latest.get("plugins") or []),
        "fetchedAt": latest.get("fetchedAt") or "",
        "error": error,
    }


def main(argv: list[str]) -> int:
    force = "--force" in argv
    result = refresh(force=force)
    sys.stdout.write(json.dumps(result, ensure_ascii=False) + "\n")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
