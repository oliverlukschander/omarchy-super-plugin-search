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

SHA = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"

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
                "listingValidatedCommit": SHA,
                "stars": 12,
                "hearts": 10,
                "copies": 1000,
                "status": "Available",
                "version": "1.4.0",
                "listedAt": "2026-07-01T00:00:00Z",
                "previewImage": "assets/img/plugins/pulse.webp",
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
                "listingValidatedCommit": SHA,
                "stars": 61,
                "hearts": 50,
                "copies": 100,
                "status": "Available",
                "version": "2.0.0",
                "listedAt": "2026-06-01T00:00:00Z",
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
                "listedAt": "2026-09-01T00:00:00Z",
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
                "listingValidatedCommit": SHA,
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
                "listingValidatedCommit": SHA,
                "stars": 3,
                "hearts": 3,
                "copies": 40,
                "status": "Manual setup",
                "version": "0.3.0",
                "listedAt": "2026-08-01T00:00:00Z",
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
        self.assertEqual(rows[0]["installCommit"], SHA)
        self.assertTrue(rows[0]["verified"])
        self.assertEqual(rows[0]["detail"], "Fred Nix · System")
        self.assertEqual(rows[0]["version"], "1.4.0")
        self.assertEqual(
            rows[0]["previewUrl"],
            "https://plugins.omarchy.org/assets/img/plugins/pulse.webp",
        )
        self.assertEqual(
            rows[0]["description"],
            "CPU RAM Disk Network and GPU in one widget",
        )
        self.assertEqual(rows[0]["enterAction"], "install")
        self.assertEqual(rows[0]["hint"], "Enter install")

    def test_installed_disables_install(self):
        rows = search.search_rows(PLUGINS, "pulse", {"nixfred.pulse"})
        self.assertEqual(rows[0]["pluginId"], "nixfred.pulse")
        self.assertTrue(rows[0]["installed"])
        self.assertFalse(rows[0]["canInstall"])
        self.assertEqual(rows[0]["detail"], "Fred Nix · System")
        self.assertEqual(rows[0]["statusLabel"], "Installed")
        self.assertEqual(rows[0]["enterAction"], "uninstall")
        self.assertEqual(rows[0]["hint"], "Enter uninstall")

    def test_manual_setup_is_searchable(self):
        rows = search.search_rows(PLUGINS, "vi mode", set())
        self.assertGreaterEqual(len(rows), 1)
        self.assertEqual(rows[0]["pluginId"], "oliverlukschander.vi-mode")
        self.assertTrue(rows[0]["canInstall"])
        self.assertEqual(
            rows[0]["installUrl"],
            "https://github.com/oliverlukschander/omarchy-vi-mode.git",
        )
        self.assertEqual(rows[0]["installCommit"], SHA)
        self.assertTrue(rows[0]["manualSetup"])
        self.assertEqual(rows[0]["statusLabel"], "Manual setup")
        self.assertEqual(rows[0]["detail"], "Oliver Lukschander · System")

    def test_built_in_is_not_installable(self):
        rows = search.search_rows(PLUGINS, "clock", set())
        self.assertEqual(rows[0]["pluginId"], "omarchy.clock")
        self.assertEqual(rows[0]["installUrl"], "")
        self.assertEqual(rows[0]["installCommit"], "")
        self.assertFalse(rows[0]["canInstall"])
        self.assertEqual(rows[0]["enterAction"], "builtin")
        self.assertFalse(rows[0]["canRemove"])

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

    def test_missing_commit_is_not_installable(self):
        row = search.row_for(
            {
                "id": "nixfred.pulse",
                "name": "Pulse",
                "status": "Available",
                "verificationStatus": "verified",
                "installCommand": "omarchy plugin add https://github.com/nixfred/pulse.git --enable",
                "repo": "https://github.com/nixfred/pulse",
            },
            installed=False,
        )
        self.assertEqual(row["installUrl"], "")
        self.assertEqual(row["installCommit"], "")
        self.assertFalse(row["canInstall"])

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

    def test_new_mode_sorts_by_listed_at(self):
        rows = search.search_rows(PLUGINS, "", set(), mode="new")
        self.assertEqual(
            [row["pluginId"] for row in rows],
            [
                "omarchy.clock",
                "oliverlukschander.vi-mode",
                "nixfred.pulse",
                "b.okomart",
            ],
        )

    def test_fuzzy_name_and_short_id_rank_below_real_hits(self):
        pulse = next(plugin for plugin in PLUGINS if plugin["id"] == "nixfred.pulse")
        self.assertEqual(search.score_one(pulse, "pulse"), 1000)
        self.assertEqual(search.score_one(pulse, "pulsx"), search.FUZZY_SCORE)
        self.assertLess(search.FUZZY_SCORE, 400)
        rows = search.search_rows(PLUGINS, "pulsx", set())
        self.assertEqual([row["pluginId"] for row in rows], ["nixfred.pulse"])
        self.assertEqual(search.search_rows(PLUGINS, "pluse", set()), [])
        self.assertEqual(search.search_rows(PLUGINS, "widgt", set()), [])
        self.assertIsNone(search.score_one(pulse, "frad"))
        self.assertEqual(
            [row["pluginId"] for row in search.search_rows(PLUGINS, "okomrt", set())],
            ["b.okomart"],
        )
        self.assertEqual(search.search_rows(PLUGINS, "okomrat", set()), [])
        self.assertEqual(search.search_rows(PLUGINS, "abc", set()), [])
        self.assertEqual(
            [row["pluginId"] for row in search.search_rows(PLUGINS, "pulsx disk", set())],
            ["nixfred.pulse"],
        )
        self.assertEqual(search.search_rows(PLUGINS, "pulsx nope", set()), [])

    def test_preview_url_stays_on_the_marketplace(self):
        self.assertEqual(
            search.preview_url("assets/img/plugins/pulse.webp"),
            "https://plugins.omarchy.org/assets/img/plugins/pulse.webp",
        )
        self.assertEqual(search.preview_url("../etc/passwd"), "")
        self.assertEqual(search.preview_url("https://evil.example/a.webp"), "")
        self.assertEqual(search.preview_url("/assets/a.webp"), "")
        self.assertEqual(search.preview_url(""), "")
        self.assertEqual(search.cache_preview("https://evil.example/a.webp"), "")
        self.assertEqual(
            search.cache_preview("https://plugins.omarchy.org/../etc/passwd"),
            "",
        )

    def test_update_status_when_head_differs(self):
        other = "b" * 40
        rows = search.search_rows(
            PLUGINS,
            "pulse",
            {"nixfred.pulse"},
            heads={"nixfred.pulse": other},
        )
        self.assertEqual(rows[0]["statusLabel"], "Update")
        self.assertEqual(rows[0]["enterAction"], "update")
        self.assertTrue(rows[0]["canUpdate"])
        self.assertFalse(rows[0]["canInstall"])
        self.assertEqual(rows[0]["detail"], "Fred Nix · System")
        self.assertEqual(rows[0]["hint"], "Enter update")

    def test_matching_head_stays_installed(self):
        rows = search.search_rows(
            PLUGINS,
            "pulse",
            {"nixfred.pulse"},
            heads={"nixfred.pulse": SHA},
        )
        self.assertEqual(rows[0]["enterAction"], "uninstall")
        self.assertEqual(rows[0]["statusLabel"], "Installed")
        self.assertEqual(rows[0]["hint"], "Enter uninstall")
        self.assertFalse(rows[0]["canUpdate"])

    def test_unreadable_head_is_not_installed_or_updated(self):
        rows = search.search_rows(PLUGINS, "pulse", {"nixfred.pulse"}, heads={})
        self.assertEqual(rows[0]["enterAction"], "uninstall")
        self.assertFalse(rows[0]["canUpdate"])
        self.assertFalse(rows[0]["canInstall"])
        self.assertEqual(rows[0]["hint"], "Enter uninstall")

    def test_installed_mode_lists_third_party_outside_the_catalog(self):
        records = [
            {"id": "nixfred.pulse", "name": "Pulse", "enabled": True, "firstParty": False},
            {"id": "omarchy.clock", "name": "Clock", "enabled": True, "firstParty": True},
            {"id": "local.custom", "name": "Custom", "enabled": False, "firstParty": False},
            {
                "id": "sketchy.unverified-clock",
                "name": "Pulse Clone",
                "enabled": True,
                "firstParty": False,
            },
        ]
        rows = search.search_rows(
            PLUGINS,
            "",
            set(),
            mode="installed",
            installed_records=records,
            heads={"nixfred.pulse": SHA, "sketchy.unverified-clock": "b" * 40},
        )
        self.assertEqual(
            [row["pluginId"] for row in rows],
            ["local.custom", "nixfred.pulse", "sketchy.unverified-clock"],
        )
        self.assertEqual(rows[0]["detail"], "local.custom · disabled")
        self.assertEqual(rows[1]["detail"], "nixfred.pulse · enabled")
        self.assertTrue(rows[0]["canRemove"])
        self.assertFalse(any(row["pluginId"] == "omarchy.clock" for row in rows))
        narrowed = search.search_rows(
            PLUGINS,
            "custom",
            set(),
            mode="installed",
            installed_records=records,
            category="System",
        )
        self.assertEqual(narrowed, [])
        system = search.search_rows(
            PLUGINS,
            "",
            set(),
            mode="installed",
            installed_records=records,
            category="System",
        )
        self.assertEqual(
            [row["pluginId"] for row in system],
            ["nixfred.pulse", "sketchy.unverified-clock"],
        )

    def test_updates_are_installed_and_behind_a_verified_sha(self):
        records = [
            {"id": "nixfred.pulse", "name": "Pulse", "enabled": True, "firstParty": False},
            {"id": "b.okomart", "name": "Okomart", "enabled": False, "firstParty": False},
            {
                "id": "sketchy.unverified-clock",
                "name": "Pulse Clone",
                "enabled": True,
                "firstParty": False,
            },
            {"id": "local.custom", "name": "Custom", "enabled": True, "firstParty": False},
        ]
        other = "b" * 40
        rows = search.search_rows(
            PLUGINS,
            "",
            set(),
            mode="updates",
            installed_records=records,
            heads={
                "nixfred.pulse": other,
                "b.okomart": SHA,
                "sketchy.unverified-clock": other,
            },
        )
        self.assertEqual([row["pluginId"] for row in rows], ["nixfred.pulse"])
        self.assertEqual(rows[0]["detail"], "nixfred.pulse · enabled")
        desktop = search.search_rows(
            PLUGINS,
            "",
            set(),
            mode="updates",
            installed_records=records,
            heads={"nixfred.pulse": other},
            category="Desktop",
        )
        self.assertEqual(desktop, [])

    def test_installed_mode_is_not_the_popular_cap(self):
        plugins = []
        records = []
        for index in range(130):
            plugin_id = f"ex.p{index:03d}"
            plugins.append(
                {
                    "id": plugin_id,
                    "name": f"Plugin {index:03d}",
                    "status": "Available",
                    "verificationStatus": "verified",
                    "hearts": 130 - index,
                    "category": "System",
                }
            )
            records.append(
                {
                    "id": plugin_id,
                    "name": f"Plugin {index:03d}",
                    "enabled": True,
                    "firstParty": False,
                }
            )
        self.assertEqual(len(search.search_rows(plugins, "", set(), mode="popular")), 120)
        self.assertEqual(
            len(
                search.search_rows(
                    plugins,
                    "",
                    set(),
                    mode="installed",
                    installed_records=records,
                )
            ),
            130,
        )

    def test_cli_new_mode_and_unknown_mode(self):
        folder = ROOT / "tests" / ".tmp"
        folder.mkdir(exist_ok=True)
        index_file = folder / "search-index-new.json"
        index_file.write_text(
            json.dumps({"plugins": PLUGINS, "fetchedAt": "2026-09-19T01:00:00Z"}),
            encoding="utf-8",
        )
        from io import StringIO
        from contextlib import redirect_stdout

        buf = StringIO()
        with redirect_stdout(buf):
            code = search.main(
                ["--mode", "new", "--index", str(index_file), "--installed-ids", ""]
            )
        self.assertEqual(code, 0)
        ids = [row["pluginId"] for row in json.loads(buf.getvalue())]
        self.assertEqual(ids[0], "omarchy.clock")
        self.assertEqual(search.main(["--mode", "nope"]), 2)


if __name__ == "__main__":
    unittest.main()
