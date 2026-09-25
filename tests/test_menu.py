#!/usr/bin/python3
from __future__ import annotations

import importlib
import os
import subprocess
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

    def test_bind_is_opt_in_and_removes_only_its_line(self):
        folder = ROOT / "tests" / ".tmp"
        folder.mkdir(exist_ok=True)
        menu = folder / "omarchy-menu.jsonc"
        bindings = folder / "bindings.lua"
        menu.write_text('{\n  "setup.vi-mode": {"label":"Vi Mode"},\n}\n', encoding="utf-8")
        bindings.write_text(
            'o.bind("SUPER + SHIFT + R", "SSH", "true")\n',
            encoding="utf-8",
        )
        os.environ["OMARCHY_MENU_PATH"] = str(menu)
        os.environ["OMARCHY_BINDINGS_PATH"] = str(bindings)
        import menu as menu_mod

        importlib.reload(menu_mod)
        menu_mod.MENU = menu
        menu_mod.BINDINGS = bindings
        before = bindings.read_text(encoding="utf-8")
        menu_mod.install()
        self.assertEqual(bindings.read_text(encoding="utf-8"), before)
        self.assertIn('"setup.plugin.search"', menu.read_text(encoding="utf-8"))
        menu_mod.bind()
        bound = bindings.read_text(encoding="utf-8")
        self.assertIn('o.bind("SUPER + SHIFT + R"', bound)
        self.assertEqual(bound.count("SUPER + CTRL + M"), 1)
        self.assertIn("oliverlukschander.super-plugin-search", bound)
        menu_mod.bind()
        self.assertEqual(bindings.read_text(encoding="utf-8").count("SUPER + CTRL + M"), 1)
        menu_mod.unbind()
        leftover = bindings.read_text(encoding="utf-8")
        self.assertNotIn("SUPER + CTRL + M", leftover)
        self.assertIn('o.bind("SUPER + SHIFT + R"', leftover)
        self.assertIn('"setup.vi-mode"', menu.read_text(encoding="utf-8"))

    def test_bind_refuses_a_taken_chord(self):
        folder = ROOT / "tests" / ".tmp"
        bindings = folder / "bindings-taken.lua"
        bindings.write_text(
            'o.bind("SUPER + CTRL + M", "Something else", "true")\n',
            encoding="utf-8",
        )
        os.environ["OMARCHY_BINDINGS_PATH"] = str(bindings)
        import menu as menu_mod

        importlib.reload(menu_mod)
        menu_mod.BINDINGS = bindings
        with self.assertRaises(SystemExit):
            menu_mod.bind()
        self.assertNotIn("super-plugin-search", bindings.read_text(encoding="utf-8"))

    def test_install_sh_default_does_not_write_the_binding(self):
        folder = ROOT / "tests" / ".tmp" / "install-sh"
        if folder.exists():
            for child in folder.iterdir():
                child.unlink()
        folder.mkdir(parents=True, exist_ok=True)
        menu = folder / "menu.jsonc"
        bindings = folder / "bindings.lua"
        menu.write_text("{}\n", encoding="utf-8")
        bindings.write_text("-- keep\n", encoding="utf-8")
        env = os.environ.copy()
        env["OMARCHY_MENU_PATH"] = str(menu)
        env["OMARCHY_BINDINGS_PATH"] = str(bindings)
        subprocess.check_call(["bash", str(ROOT / "install.sh")], env=env)
        self.assertEqual(bindings.read_text(encoding="utf-8"), "-- keep\n")
        self.assertIn("Search plugins", menu.read_text(encoding="utf-8"))
        completed = subprocess.run(
            ["bash", str(ROOT / "install.sh"), "--bind"],
            env=env,
            check=True,
            text=True,
            capture_output=True,
        )
        self.assertIn("Super+Ctrl+M opens Search plugins.", completed.stdout)
        self.assertIn("SUPER + CTRL + M", bindings.read_text(encoding="utf-8"))
        self.assertIn("-- keep", bindings.read_text(encoding="utf-8"))
        subprocess.check_call(["bash", str(ROOT / "uninstall.sh")], env=env)
        self.assertNotIn("SUPER + CTRL + M", bindings.read_text(encoding="utf-8"))
        self.assertIn("-- keep", bindings.read_text(encoding="utf-8"))
        self.assertNotIn("setup.plugin.search", menu.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
