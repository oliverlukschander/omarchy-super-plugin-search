#!/usr/bin/python3
"""Add or remove the Setup → Plugins → Search plugins row."""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from safe_file import atomic_write, die, read_text

_CONFIG = Path(os.environ.get("XDG_CONFIG_HOME") or (Path.home() / ".config"))
MENU = Path(os.environ.get("OMARCHY_MENU_PATH") or (_CONFIG / "omarchy" / "extensions" / "omarchy-menu.jsonc"))
MARKER = '"setup.plugin.search"'
ROW = (
    '  "setup.plugin.search": {'
    '"icon":"󰍉",'
    '"label":"Search plugins",'
    '"description":"Search the Omarchy plugin marketplace",'
    '"action":"omarchy-shell shell summon oliverlukschander.super-plugin-search \'{}\'"'
    "},\n"
)


def _with_row(text: str) -> str:
    if MARKER in text:
        return "".join(line if MARKER not in line else ROW for line in text.splitlines(keepends=True))
    idx = text.rfind("}")
    if idx == -1:
        return "{\n" + ROW + "}\n"
    return text[:idx] + ROW + text[idx:]


def _without_row(text: str) -> str:
    return "".join(line for line in text.splitlines(keepends=True) if MARKER not in line)


def install() -> None:
    atomic_write(MENU, _with_row(read_text(MENU, missing="{\n}\n")))


def uninstall() -> None:
    text = read_text(MENU, missing="")
    if not text:
        return
    atomic_write(MENU, _without_row(text))


if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else "install"
    if action == "uninstall":
        uninstall()
    elif action == "install":
        install()
    else:
        die("usage: menu.py [install|uninstall]")
