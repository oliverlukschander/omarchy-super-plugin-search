#!/usr/bin/python3
"""Clone a marketplace plugin at its approved commit and offer setup."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from catalog import approved_commit

PLUGINS = Path(os.environ.get("XDG_CONFIG_HOME") or (Path.home() / ".config")) / "omarchy" / "plugins"
SETUP_NAMES = ("setup", "install.sh")
GIT_TIMEOUT = 120
PLUGIN_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


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


def valid_plugin_id(value: str) -> bool:
    return bool(PLUGIN_ID.fullmatch(value)) and ".." not in value


def contained_script(folder: Path, name: str) -> Path | None:
    try:
        root = folder.resolve()
    except OSError:
        return None
    path = folder / name
    if not path.is_file() or not os.access(path, os.X_OK):
        return None
    try:
        resolved = path.resolve()
    except OSError:
        return None
    if resolved.is_relative_to(root):
        return resolved
    return None


def setup_script(folder: Path) -> Path | None:
    for name in SETUP_NAMES:
        found = contained_script(folder, name)
        if found is not None:
            return found
    return None


def uninstall_script(folder: Path) -> Path | None:
    return contained_script(folder, "uninstall.sh")


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


def pin_checkout(folder: Path, sha: str, *, fetch: bool = False) -> None:
    if fetch:
        git(folder, "fetch", "--depth", "1", "--", "origin", sha)
    else:
        try:
            git(folder, "cat-file", "-e", f"{sha}^{{commit}}")
        except subprocess.CalledProcessError:
            git(folder, "fetch", "--depth", "1", "--", "origin", sha)
    git(folder, "checkout", "--detach", sha)
    head = git(folder, "rev-parse", "HEAD", capture=True).lower()
    if head != sha:
        raise RuntimeError(f"checked out {head}, expected {sha}")


def worktree_clean(folder: Path) -> bool:
    return git(folder, "status", "--porcelain", capture=True) == ""


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


def plugin_root() -> Path:
    return Path(os.environ.get("SEARCH_PLUGIN_ROOT") or PLUGINS)


def refuse_sha(sha: str) -> int:
    if sha:
        return 0
    print(
        "refusing to continue: marketplace-approved commit SHA is missing "
        "or is not a full 40-character SHA",
        file=sys.stderr,
    )
    return 2


def install_snapshot(url: str, sha: str) -> int:
    root = plugin_root()
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


def update_snapshot(url: str, sha: str) -> int:
    root = plugin_root()
    folder = folder_for_url(url, plugin_dirs(root))
    if folder is None:
        print("refusing to update: plugin folder not found", file=sys.stderr)
        return 1
    try:
        head = git(folder, "rev-parse", "HEAD", capture=True).lower()
    except (OSError, subprocess.SubprocessError) as exc:
        print(f"refusing to update: could not read HEAD: {exc}", file=sys.stderr)
        return 1
    if approved_commit(head) == sha:
        print("Already installed")
        return 0
    try:
        if not worktree_clean(folder):
            print("refusing to update: worktree is dirty", file=sys.stderr)
            return 1
        pin_checkout(folder, sha, fetch=True)
    except (OSError, subprocess.SubprocessError, RuntimeError) as exc:
        print(f"refusing to update: could not pin marketplace commit {sha}: {exc}", file=sys.stderr)
        return 1
    return subprocess.call(["omarchy", "plugin", "enable", plugin_id(folder)])


def remove_plugin(plugin_id_value: str) -> int:
    if not valid_plugin_id(plugin_id_value):
        print("refusing to remove: invalid plugin id", file=sys.stderr)
        return 2
    root = plugin_root()
    folder = root / plugin_id_value
    if folder.is_dir():
        script = uninstall_script(folder)
        if script is not None:
            try:
                code = subprocess.call([str(script)], timeout=GIT_TIMEOUT)
            except (OSError, subprocess.SubprocessError) as exc:
                print(f"refusing to remove: uninstall failed: {exc}", file=sys.stderr)
                return 1
            if code != 0:
                print("refusing to remove: uninstall failed", file=sys.stderr)
                return code
    return subprocess.call(["omarchy", "plugin", "remove", plugin_id_value, "--yes"])


def main(argv: list[str]) -> int:
    args = list(argv)
    if args and args[0] in ("install", "update", "remove"):
        command = args.pop(0)
    else:
        command = "install"
    if command == "remove":
        if len(args) != 1:
            print("usage: install.py remove <plugin-id>", file=sys.stderr)
            return 2
        return remove_plugin(args[0])
    if len(args) < 2:
        print(f"usage: install.py {command} <git-url> <commit-sha>", file=sys.stderr)
        return 2
    url = args[0]
    sha = approved_commit(args[1])
    refused = refuse_sha(sha)
    if refused:
        return refused
    if command == "update":
        return update_snapshot(url, sha)
    return install_snapshot(url, sha)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
