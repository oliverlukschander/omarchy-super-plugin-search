#!/usr/bin/python3
from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import install  # noqa: E402

SHA = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
URL = "https://github.com/thisisgm/omarchy-pods.git"


class InstallTests(unittest.TestCase):
    def setUp(self) -> None:
        self.folder = ROOT / "tests" / ".tmp" / self._testMethodName
        if self.folder.exists():
            shutil.rmtree(self.folder)
        self.folder.mkdir(parents=True)
        os.environ["SEARCH_PLUGIN_ROOT"] = str(self.folder)
        os.environ["OMARCHY_PATH"] = "/usr/share/omarchy"

    def _write_plugin(self, added: Path, *, setup: bool = False) -> None:
        added.mkdir()
        (added / "manifest.json").write_text(
            json.dumps({"id": added.name, "name": "AirPods"}),
            encoding="utf-8",
        )
        if setup:
            path = added / "setup"
            path.write_text("#!/bin/bash\necho ran\n", encoding="utf-8")
            path.chmod(path.stat().st_mode | stat.S_IEXEC)

    def test_refuses_without_sha(self):
        with mock.patch("install.subprocess.call") as call:
            code = install.main([URL])
        self.assertEqual(code, 2)
        call.assert_not_called()

    def test_refuses_invalid_sha(self):
        with mock.patch("install.subprocess.call") as call:
            code = install.main([URL, "abc"])
        self.assertEqual(code, 2)
        call.assert_not_called()

    def test_pins_then_enables_and_notifies(self):
        added = self.folder / "io.github.thisisgm.omapods"
        calls: list[list[str]] = []

        def fake_call(cmd, *args, **kwargs):
            calls.append(list(cmd))
            if cmd[:4] == ["omarchy", "plugin", "add", URL]:
                self.assertEqual(cmd, ["omarchy", "plugin", "add", URL, "--yes"])
                self._write_plugin(added, setup=True)
                return 0
            if cmd[:3] == ["omarchy", "plugin", "enable"]:
                self.assertEqual(cmd, ["omarchy", "plugin", "enable", added.name])
                return 0
            if cmd and str(cmd[0]).endswith("omarchy-notification-send"):
                return 0
            self.fail(f"unexpected command {cmd}")

        def fake_check_call(cmd, *args, **kwargs):
            calls.append(list(cmd))
            if cmd[:2] == ["git", "-C"] and "cat-file" in cmd:
                return 0
            if cmd[:2] == ["git", "-C"] and "checkout" in cmd:
                self.assertIn("--detach", cmd)
                self.assertIn(SHA, cmd)
                return 0
            self.fail(f"unexpected command {cmd}")

        def fake_check_output(cmd, *args, **kwargs):
            calls.append(list(cmd))
            if cmd[:2] == ["git", "-C"] and "rev-parse" in cmd:
                return SHA + "\n"
            self.fail(f"unexpected command {cmd}")

        with (
            mock.patch("install.subprocess.call", side_effect=fake_call),
            mock.patch("install.subprocess.check_call", side_effect=fake_check_call),
            mock.patch("install.subprocess.check_output", side_effect=fake_check_output),
        ):
            code = install.main([URL, SHA])
        self.assertEqual(code, 0)
        self.assertTrue(any(cmd[:3] == ["omarchy", "plugin", "enable"] for cmd in calls))
        notify = next(cmd for cmd in calls if str(cmd[0]).endswith("omarchy-notification-send"))
        self.assertEqual(notify[1:6], ["-u", "critical", "-g", "󰐱", "Finish installing AirPods"])
        self.assertEqual(Path(notify[9]), (added / "setup").resolve())
        self.assertFalse(any(cmd[:3] == ["omarchy", "plugin", "remove"] for cmd in calls))

    def test_skips_setup_when_missing(self):
        added = self.folder / "example.plugin"

        def fake_call(cmd, *args, **kwargs):
            if cmd[:3] == ["omarchy", "plugin", "add"]:
                self._write_plugin(added)
                return 0
            if cmd[:3] == ["omarchy", "plugin", "enable"]:
                return 0
            self.fail(f"unexpected command {cmd}")

        def fake_check_call(cmd, *args, **kwargs):
            return 0

        def fake_check_output(cmd, *args, **kwargs):
            return SHA + "\n"

        with (
            mock.patch("install.subprocess.call", side_effect=fake_call),
            mock.patch("install.subprocess.check_call", side_effect=fake_check_call),
            mock.patch("install.subprocess.check_output", side_effect=fake_check_output),
        ):
            code = install.main([URL, SHA])
        self.assertEqual(code, 0)

    def test_discards_when_pin_fails(self):
        added = self.folder / "example.plugin"
        calls: list[list[str]] = []

        def fake_call(cmd, *args, **kwargs):
            calls.append(list(cmd))
            if cmd[:3] == ["omarchy", "plugin", "add"]:
                self._write_plugin(added, setup=True)
                return 0
            if cmd[:3] == ["omarchy", "plugin", "remove"]:
                return 0
            self.fail(f"unexpected command {cmd}")

        def fake_check_call(cmd, *args, **kwargs):
            raise subprocess.CalledProcessError(1, cmd)

        with (
            mock.patch("install.subprocess.call", side_effect=fake_call),
            mock.patch("install.subprocess.check_call", side_effect=fake_check_call),
        ):
            code = install.main([URL, SHA])
        self.assertEqual(code, 1)
        self.assertTrue(any(cmd[:3] == ["omarchy", "plugin", "remove"] for cmd in calls))
        self.assertFalse(any(cmd[:3] == ["omarchy", "plugin", "enable"] for cmd in calls))
        self.assertFalse(added.exists())

    def test_discards_when_head_does_not_match(self):
        added = self.folder / "example.plugin"
        calls: list[list[str]] = []

        def fake_call(cmd, *args, **kwargs):
            calls.append(list(cmd))
            if cmd[:3] == ["omarchy", "plugin", "add"]:
                self._write_plugin(added)
                return 0
            if cmd[:3] == ["omarchy", "plugin", "remove"]:
                return 0
            self.fail(f"unexpected command {cmd}")

        def fake_check_call(cmd, *args, **kwargs):
            return 0

        def fake_check_output(cmd, *args, **kwargs):
            return "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb\n"

        with (
            mock.patch("install.subprocess.call", side_effect=fake_call),
            mock.patch("install.subprocess.check_call", side_effect=fake_check_call),
            mock.patch("install.subprocess.check_output", side_effect=fake_check_output),
        ):
            code = install.main([URL, SHA])
        self.assertEqual(code, 1)
        self.assertTrue(any(cmd[:3] == ["omarchy", "plugin", "remove"] for cmd in calls))
        self.assertFalse(added.exists())

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

    def _existing_plugin(self) -> Path:
        added = self.folder / "example.plugin"
        self._write_plugin(added)
        return added

    def _git_output(self, head: str, status: str = ""):
        def fake_check_output(cmd, *args, **kwargs):
            if "get-url" in cmd:
                return URL + "\n"
            if "rev-parse" in cmd:
                return head + "\n"
            if "status" in cmd:
                return status
            self.fail(f"unexpected command {cmd}")

        return fake_check_output

    def test_update_reports_already_installed_at_the_same_sha(self):
        self._existing_plugin()
        with (
            mock.patch("install.subprocess.call") as call,
            mock.patch("install.subprocess.check_call") as check_call,
            mock.patch("install.subprocess.check_output", side_effect=self._git_output(SHA)),
        ):
            code = install.main(["update", URL, SHA])
        self.assertEqual(code, 0)
        call.assert_not_called()
        check_call.assert_not_called()

    def test_update_pins_clean_worktree_without_deleting(self):
        added = self._existing_plugin()
        other = "b" * 40
        pinned = {"done": False}
        calls: list[list[str]] = []

        def fake_call(cmd, *args, **kwargs):
            calls.append(list(cmd))
            if cmd[:3] == ["omarchy", "plugin", "enable"]:
                self.assertEqual(cmd, ["omarchy", "plugin", "enable", "example.plugin"])
                return 0
            self.fail(f"unexpected command {cmd}")

        def fake_check_call(cmd, *args, **kwargs):
            calls.append(list(cmd))
            if "fetch" in cmd:
                self.assertIn(SHA, cmd)
                return 0
            if "checkout" in cmd:
                self.assertIn("--detach", cmd)
                self.assertIn(SHA, cmd)
                pinned["done"] = True
                return 0
            self.fail(f"unexpected command {cmd}")

        def fake_check_output(cmd, *args, **kwargs):
            if "get-url" in cmd:
                return URL + "\n"
            if "rev-parse" in cmd:
                return (SHA if pinned["done"] else other) + "\n"
            if "status" in cmd:
                return ""
            self.fail(f"unexpected command {cmd}")

        with (
            mock.patch("install.subprocess.call", side_effect=fake_call),
            mock.patch("install.subprocess.check_call", side_effect=fake_check_call),
            mock.patch("install.subprocess.check_output", side_effect=fake_check_output),
        ):
            code = install.main(["update", URL, SHA])
        self.assertEqual(code, 0)
        self.assertTrue(added.exists())
        self.assertTrue(any("fetch" in cmd for cmd in calls))
        self.assertTrue(any(cmd[:3] == ["omarchy", "plugin", "enable"] for cmd in calls))
        self.assertFalse(any(cmd[:3] == ["omarchy", "plugin", "remove"] for cmd in calls))

    def test_update_refuses_dirty_worktree(self):
        added = self._existing_plugin()
        with (
            mock.patch("install.subprocess.call") as call,
            mock.patch("install.subprocess.check_call") as check_call,
            mock.patch(
                "install.subprocess.check_output",
                side_effect=self._git_output("b" * 40, " M Overlay.qml\n"),
            ),
        ):
            code = install.main(["update", URL, SHA])
        self.assertEqual(code, 1)
        self.assertTrue(added.exists())
        call.assert_not_called()
        check_call.assert_not_called()

    def test_update_pin_failure_keeps_the_folder(self):
        added = self._existing_plugin()

        def fake_check_call(cmd, *args, **kwargs):
            raise subprocess.CalledProcessError(1, cmd)

        with (
            mock.patch("install.subprocess.call") as call,
            mock.patch("install.subprocess.check_call", side_effect=fake_check_call),
            mock.patch(
                "install.subprocess.check_output",
                side_effect=self._git_output("b" * 40, ""),
            ),
        ):
            code = install.main(["update", URL, SHA])
        self.assertEqual(code, 1)
        self.assertTrue(added.exists())
        call.assert_not_called()

    def test_update_refuses_without_sha(self):
        with mock.patch("install.subprocess.call") as call:
            code = install.main(["update", URL, "abc"])
        self.assertEqual(code, 2)
        call.assert_not_called()

    def test_remove_runs_uninstall_before_omarchy(self):
        added = self._existing_plugin()
        script = added / "uninstall.sh"
        script.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        script.chmod(script.stat().st_mode | stat.S_IEXEC)
        order: list[list[str]] = []

        def fake_call(cmd, *args, **kwargs):
            order.append(list(cmd))
            if str(cmd[0]).endswith("uninstall.sh"):
                return 0
            if cmd[:3] == ["omarchy", "plugin", "remove"]:
                self.assertEqual(cmd, ["omarchy", "plugin", "remove", "example.plugin", "--yes"])
                return 0
            self.fail(f"unexpected command {cmd}")

        with mock.patch("install.subprocess.call", side_effect=fake_call):
            code = install.main(["remove", "example.plugin"])
        self.assertEqual(code, 0)
        self.assertTrue(str(order[0][0]).endswith("uninstall.sh"))
        self.assertEqual(order[1][:3], ["omarchy", "plugin", "remove"])

    def test_remove_aborts_when_uninstall_fails(self):
        added = self._existing_plugin()
        script = added / "uninstall.sh"
        script.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
        script.chmod(script.stat().st_mode | stat.S_IEXEC)

        def fake_call(cmd, *args, **kwargs):
            if str(cmd[0]).endswith("uninstall.sh"):
                return 7
            self.fail(f"unexpected command {cmd}")

        with mock.patch("install.subprocess.call", side_effect=fake_call):
            code = install.main(["remove", "example.plugin"])
        self.assertEqual(code, 7)
        self.assertTrue(added.exists())

    def test_remove_skips_uninstall_that_is_not_executable(self):
        added = self._existing_plugin()
        script = added / "uninstall.sh"
        script.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")

        def fake_call(cmd, *args, **kwargs):
            self.assertEqual(cmd, ["omarchy", "plugin", "remove", "example.plugin", "--yes"])
            return 0

        with mock.patch("install.subprocess.call", side_effect=fake_call):
            code = install.main(["remove", "example.plugin"])
        self.assertEqual(code, 0)

    def test_remove_refuses_bad_id(self):
        with mock.patch("install.subprocess.call") as call:
            code = install.main(["remove", "../example"])
        self.assertEqual(code, 2)
        call.assert_not_called()


if __name__ == "__main__":
    unittest.main()
