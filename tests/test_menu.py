#!/usr/bin/python3
from __future__ import annotations

import importlib
import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


class MenuTests(unittest.TestCase):
    def test_install_and_uninstall_keeps_other_rows(self):
        folder = ROOT / "tests" / ".tmp"
        folder.mkdir(exist_ok=True)
        menu = folder / "omarchy-menu.jsonc"
        menu.write_text(
            '{\n  "setup.vi-mode": {"icon":"","label":"Vi Mode","action":"true"},\n}\n',
            encoding="utf-8",
        )
        os.environ["OMARCHY_MENU_PATH"] = str(menu)
        import menu as menu_mod

        importlib.reload(menu_mod)
        menu_mod.MENU = menu
        menu_mod.install()
        text = menu.read_text(encoding="utf-8")
        self.assertIn('"setup.plugin.search"', text)
        self.assertIn("Search plugins", text)
        self.assertIn('"setup.vi-mode"', text)
        menu_mod.install()
        self.assertEqual(menu.read_text(encoding="utf-8").count('"setup.plugin.search"'), 1)
        menu_mod.uninstall()
        leftover = menu.read_text(encoding="utf-8")
        self.assertNotIn('"setup.plugin.search"', leftover)
        self.assertIn('"setup.vi-mode"', leftover)


if __name__ == "__main__":
    unittest.main()
