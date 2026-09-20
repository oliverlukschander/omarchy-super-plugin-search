#!/usr/bin/python3
from __future__ import annotations

import json
import os
import shutil
import stat
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import install  # noqa: E402


class InstallTests(unittest.TestCase):
    def setUp(self) -> None:
        self.folder = ROOT / "tests" / ".tmp" / self._testMethodName
        if self.folder.exists():
            shutil.rmtree(self.folder)
        self.folder.mkdir(parents=True)
        os.environ["SEARCH_PLUGIN_ROOT"] = str(self.folder)
        os.environ["OMARCHY_PATH"] = "/usr/share/omarchy"

    def test_notifies_when_setup_present(self):
        added = self.folder / "io.github.thisisgm.omapods"
        calls: list[list[str]] = []

        def fake_call(cmd, *args, **kwargs):
            calls.append(list(cmd))
            if cmd[:3] == ["omarchy", "plugin", "add"]:
                added.mkdir()
                (added / "manifest.json").write_text(
                    json.dumps({"name": "AirPods"}),
                    encoding="utf-8",
                )
                setup = added / "setup"
                setup.write_text("#!/bin/bash\necho ran\n", encoding="utf-8")
                setup.chmod(setup.stat().st_mode | stat.S_IEXEC)
                return 0
            if cmd and str(cmd[0]).endswith("omarchy-notification-send"):
                return 0
            self.fail(f"unexpected command {cmd}")

        with mock.patch("install.subprocess.call", side_effect=fake_call):
            code = install.main(["https://github.com/thisisgm/omarchy-pods.git"])
        self.assertEqual(code, 0)
        notify = next(cmd for cmd in calls if str(cmd[0]).endswith("omarchy-notification-send"))
        self.assertEqual(notify[1:6], ["-u", "critical", "-g", "󰐱", "Finish installing AirPods"])
        self.assertEqual(notify[6], "Click to run the extra setup step.")
        self.assertEqual(notify[7], "--exec")
        self.assertTrue(str(notify[8]).endswith("omarchy-launch-floating-terminal-with-presentation"))
        self.assertEqual(Path(notify[9]), (added / "setup").resolve())
        self.assertFalse(any(cmd == [str((added / "setup").resolve())] for cmd in calls))

    def test_skips_setup_when_missing(self):
        added = self.folder / "example.plugin"

        def fake_call(cmd, *args, **kwargs):
            if cmd[:3] == ["omarchy", "plugin", "add"]:
                added.mkdir()
                return 0
            self.fail(f"unexpected command {cmd}")

        with mock.patch("install.subprocess.call", side_effect=fake_call):
            code = install.main(["https://github.com/example/plugin.git"])
        self.assertEqual(code, 0)

    def test_prefers_setup_over_install_sh(self):
        folder = self.folder / "example.plugin"
        folder.mkdir()
        for name in ("setup", "install.sh"):
            path = folder / name
            path.write_text("#!/bin/bash\n", encoding="utf-8")
            path.chmod(path.stat().st_mode | stat.S_IEXEC)
        chosen = install.setup_script(folder)
        self.assertIsNotNone(chosen)
        self.assertEqual(chosen.name, "setup")

    def test_normalize_git_url(self):
        self.assertEqual(
            install.normalize_git_url("https://github.com/thisisgm/omarchy-pods.git/"),
            "https://github.com/thisisgm/omarchy-pods",
        )


if __name__ == "__main__":
    unittest.main()
