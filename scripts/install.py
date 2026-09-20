#!/usr/bin/python3
"""Clone a marketplace plugin and offer a clickable setup notification."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

PLUGINS = Path(os.environ.get("XDG_CONFIG_HOME") or (Path.home() / ".config")) / "omarchy" / "plugins"
SETUP_NAMES = ("setup", "install.sh")


def plugin_dirs(root: Path) -> set[Path]:
    if not root.is_dir():
        return set()
    return {path.resolve() for path in root.iterdir() if path.is_dir()}


def origin_url(folder: Path) -> str:
    try:
        remote = subprocess.check_output(
            ["git", "-C", str(folder), "remote", "get-url", "origin"],
            text=True,
            timeout=5,
        ).strip()
    except (OSError, subprocess.SubprocessError):
        return ""
    return normalize_git_url(remote)


def normalize_git_url(url: str) -> str:
    text = str(url or "").strip().rstrip("/")
    if text.endswith(".git"):
        text = text[:-4]
    return text


def folder_for_url(url: str, folders: set[Path]) -> Path | None:
    needle = normalize_git_url(url)
    if not needle:
        return None
    for folder in sorted(folders):
        if origin_url(folder) == needle:
            return folder
    return None


def setup_script(folder: Path) -> Path | None:
    try:
        root = folder.resolve()
    except OSError:
        return None
    for name in SETUP_NAMES:
        path = folder / name
        if not path.is_file() or not os.access(path, os.X_OK):
            continue
        try:
            resolved = path.resolve()
        except OSError:
            continue
        if resolved.is_relative_to(root):
            return resolved
    return None


def plugin_name(folder: Path) -> str:
    manifest = folder / "manifest.json"
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return folder.name
    if not isinstance(data, dict):
        return folder.name
    name = str(data.get("name") or "").strip()
    return name or folder.name


def omarchy_bin(name: str) -> str:
    root = os.environ.get("OMARCHY_PATH") or "/usr/share/omarchy"
    path = Path(root) / "bin" / name
    if path.is_file():
        return str(path)
    return shutil.which(name) or str(path)


def finish_notification_argv(name: str, setup: Path) -> list[str]:
    label = name.strip() or "plugin"
    return [
        omarchy_bin("omarchy-notification-send"),
        "-u",
        "critical",
        "-g",
        "󰐱",
        f"Finish installing {label}",
        "Click to run the extra setup step.",
        "--exec",
        omarchy_bin("omarchy-launch-floating-terminal-with-presentation"),
        str(setup),
    ]


def send_finish_notification(name: str, setup: Path) -> None:
    subprocess.call(finish_notification_argv(name, setup))


def main(argv: list[str]) -> int:
    if not argv:
        print("usage: install.py <git-url>", file=sys.stderr)
        return 2
    url = argv[0]
    root = Path(os.environ.get("SEARCH_PLUGIN_ROOT") or PLUGINS)
    before = plugin_dirs(root)
    add = subprocess.call(["omarchy", "plugin", "add", url, "--enable"])
    if add != 0:
        return add
    after = plugin_dirs(root)
    folder = next(iter(after - before), None) or folder_for_url(url, after)
    if folder is None:
        return 0
    setup = setup_script(folder)
    if setup is None:
        return 0
    name = plugin_name(folder)
    send_finish_notification(name, setup)
    print(f"Click the notification to finish installing {name}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
