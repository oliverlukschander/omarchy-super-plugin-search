#!/usr/bin/python3
"""Clone a marketplace plugin at its approved commit and offer setup."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from catalog import approved_commit

PLUGINS = Path(os.environ.get("XDG_CONFIG_HOME") or (Path.home() / ".config")) / "omarchy" / "plugins"
SETUP_NAMES = ("setup", "install.sh")
GIT_TIMEOUT = 120


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


def manifest_field(folder: Path, key: str) -> str:
    manifest = folder / "manifest.json"
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return ""
    if not isinstance(data, dict):
        return ""
    return str(data.get(key) or "").strip()


def plugin_id(folder: Path) -> str:
    return manifest_field(folder, "id") or folder.name


def plugin_name(folder: Path) -> str:
    return manifest_field(folder, "name") or folder.name


def git(folder: Path, *args: str, capture: bool = False, timeout: int = GIT_TIMEOUT) -> str:
    cmd = ["git", "-C", str(folder), *args]
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    if capture:
        return subprocess.check_output(cmd, text=True, timeout=timeout, env=env).strip()
    subprocess.check_call(cmd, timeout=timeout, env=env)
    return ""


def pin_checkout(folder: Path, sha: str) -> None:
    try:
        git(folder, "cat-file", "-e", f"{sha}^{{commit}}")
    except subprocess.CalledProcessError:
        git(folder, "fetch", "--depth", "1", "--", "origin", sha)
    git(folder, "checkout", "--detach", sha)
    head = git(folder, "rev-parse", "HEAD", capture=True).lower()
    if head != sha:
        raise RuntimeError(f"checked out {head}, expected {sha}")


def discard_plugin(folder: Path) -> None:
    ident = plugin_id(folder)
    subprocess.call(["omarchy", "plugin", "remove", ident])
    if folder.exists():
        shutil.rmtree(folder, ignore_errors=True)


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
    if len(argv) < 2:
        print("usage: install.py <git-url> <commit-sha>", file=sys.stderr)
        return 2
    url = argv[0]
    sha = approved_commit(argv[1])
    if not sha:
        print(
            "refusing to install: marketplace-approved commit SHA is missing "
            "or is not a full 40-character SHA",
            file=sys.stderr,
        )
        return 2
    root = Path(os.environ.get("SEARCH_PLUGIN_ROOT") or PLUGINS)
    before = plugin_dirs(root)
    print(f"Installing marketplace snapshot {sha}", flush=True)
    add = subprocess.call(["omarchy", "plugin", "add", url, "--yes"])
    if add != 0:
        return add
    after = plugin_dirs(root)
    folder = next(iter(after - before), None) or folder_for_url(url, after)
    if folder is None:
        print("refusing to continue: cloned plugin folder not found", file=sys.stderr)
        return 1
    try:
        pin_checkout(folder, sha)
    except (OSError, subprocess.SubprocessError, RuntimeError) as exc:
        discard_plugin(folder)
        print(f"refusing to enable: could not pin marketplace commit {sha}: {exc}", file=sys.stderr)
        return 1
    enable = subprocess.call(["omarchy", "plugin", "enable", plugin_id(folder)])
    if enable != 0:
        return enable
    setup = setup_script(folder)
    if setup is None:
        return 0
    name = plugin_name(folder)
    send_finish_notification(name, setup)
    print(f"Click the notification to finish installing {name}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
