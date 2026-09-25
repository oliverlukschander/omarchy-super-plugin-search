#!/usr/bin/python3
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import catalog  # noqa: E402


SAMPLE = {
    "generatedAt": "2026-09-19T00:00:00.000Z",
    "plugins": [
        {
            "id": "nixfred.pulse",
            "name": "Pulse",
            "description": "CPU, RAM, Disk, Network and GPU in one widget",
            "author": "Fred Nix",
            "category": "System",
            "tags": ["bar", "system"],
            "kind": "Bar widget",
            "repo": "https://github.com/nixfred/pulse",
            "installCommand": "omarchy plugin add https://github.com/nixfred/pulse.git --enable",
            "installAvailable": True,
            "verificationStatus": "verified",
            "stars": 12,
            "status": "Available",
            "previewImage": "drop-me.webp",
            "listingValidatedCommit": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
            "version": "1.4.0",
            "listedAt": "2026-07-01T00:00:00Z",
        },
        {
            "id": "lacuna.shell-suite",
            "name": "Lacuna",
            "description": "A complete visual shell",
            "author": "OldJobobo",
            "kind": "Suite",
            "repo": "https://github.com/OldJobobo/lacuna-shell",
            "installCommand": "",
            "installAvailable": False,
            "status": "Manual setup",
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
            "status": "Built in",
        },
        {"name": "missing-id"},
    ],
}


class CatalogTests(unittest.TestCase):
    def test_slim_keeps_preview_version_and_listed_at(self):
        index = catalog.slim_catalog(SAMPLE, fetched_at="2026-09-19T01:00:00Z", etag='"abc"')
        ids = [plugin["id"] for plugin in index["plugins"]]
        self.assertEqual(ids, ["nixfred.pulse", "lacuna.shell-suite", "omarchy.clock"])
        pulse = index["plugins"][0]
        self.assertEqual(pulse["previewImage"], "drop-me.webp")
        self.assertEqual(pulse["version"], "1.4.0")
        self.assertEqual(pulse["listedAt"], "2026-07-01T00:00:00Z")
        self.assertEqual(
            pulse["listingValidatedCommit"],
            "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        )
        self.assertEqual(pulse["name"], "Pulse")
        self.assertTrue(pulse["installAvailable"])
        self.assertEqual(pulse["hearts"], 0)
        self.assertEqual(pulse["copies"], 0)

    def test_approved_commit(self):
        self.assertEqual(catalog.approved_commit("A" * 40), "a" * 40)
        self.assertEqual(catalog.approved_commit("abc"), "")
        self.assertEqual(catalog.approved_commit(""), "")
        self.assertEqual(catalog.approved_commit("a" * 39), "")
        self.assertEqual(catalog.approved_commit("g" * 40), "")

    def test_default_pool(self):
        index = catalog.slim_catalog(SAMPLE, fetched_at="2026-09-19T01:00:00Z")
        pool = [plugin["id"] for plugin in index["plugins"] if catalog.in_default_pool(plugin)]
        self.assertEqual(pool, ["nixfred.pulse", "omarchy.clock"])
        self.assertEqual(catalog.present_categories(index["plugins"]), ["System"])

    def test_refresh_writes_slim_index(self):
        out = Path(self._tmp())
        body = json.dumps(SAMPLE).encode()

        stats_body = json.dumps(
            {
                "schemaVersion": 1,
                "plugins": {
                    "nixfred.pulse": {"views": 80, "copies": 12, "hearts": 4}
                },
            }
        ).encode()

        def fetcher(url, etag):
            if url == catalog.STATS_URL:
                return 200, stats_body, '"stats-1"'
            self.assertEqual(url, catalog.CATALOG_URL)
            self.assertEqual(etag, "")
            return 200, body, '"etag-1"'

        result = catalog.refresh(force=True, path=out, fetcher=fetcher)
        self.assertTrue(result["ok"])
        self.assertTrue(result["refreshed"])
        self.assertEqual(result["count"], 3)
        saved = catalog.load_index(out)
        self.assertIsNotNone(saved)
        self.assertEqual(len(saved["plugins"]), 3)
        self.assertEqual(saved["etag"], '"etag-1"')
        pulse = next(plugin for plugin in saved["plugins"] if plugin["id"] == "nixfred.pulse")
        self.assertEqual(pulse["hearts"], 4)
        self.assertEqual(pulse["copies"], 12)

        def not_modified(url, etag):
            if url == catalog.STATS_URL:
                return 304, b"", '"stats-1"'
            self.assertEqual(etag, '"etag-1"')
            return 304, b"", '"etag-1"'

        again = catalog.refresh(force=True, path=out, fetcher=not_modified)
        self.assertTrue(again["ok"])
        self.assertTrue(again["refreshed"])

    def test_failed_fetch_keeps_cache(self):
        out = Path(self._tmp())
        catalog.write_index(
            out,
            catalog.slim_catalog(SAMPLE, fetched_at="2026-01-01T00:00:00Z", etag='"old"'),
        )

        def boom(url, etag):
            raise TimeoutError("timed out")

        result = catalog.refresh(force=True, path=out, fetcher=boom)
        self.assertTrue(result["ok"])
        self.assertFalse(result["refreshed"])
        self.assertIn("timed out", result["error"])
        saved = catalog.load_index(out)
        self.assertEqual(saved["etag"], '"old"')

    def _tmp(self) -> str:
        folder = ROOT / "tests" / ".tmp"
        folder.mkdir(exist_ok=True)
        path = folder / (self._testMethodName + ".json")
        if path.exists():
            path.unlink()
        return str(path)


if __name__ == "__main__":
    unittest.main()
