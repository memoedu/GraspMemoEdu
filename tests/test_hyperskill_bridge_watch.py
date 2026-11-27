from contextlib import nullcontext
from datetime import datetime, timezone
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch

from scripts import hyperskill_bridge_watch as watch


class BridgeWatchTests(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        self.config = root / "config.json"
        self.config.write_text(json.dumps({"port": 18769, "origins": ["https://example.org"]}))
        self.health = dict(ready=True, provider="hyperskill", pid=4321, instance_id="a" * 32)
        instant = datetime.now(timezone.utc)
        self.marker = root / "bridge-instance.json"
        self.marker.write_text(json.dumps(dict(pid=4321, started_at=instant.isoformat(), instance_id="a" * 32)))
        (root / "bridge.pid").write_text("4321\n")
        node = root / "node.exe"
        script = Path(watch.__file__).with_name("hyperskill_bridge.mjs").resolve()
        self.process = Mock()
        self.process.cmdline.return_value = [str(node), str(script), str(self.config)]
        self.process.exe.return_value = str(node)
        self.process.create_time.return_value = instant.timestamp()
        self.process.oneshot.return_value = nullcontext()
        self.process.is_running.return_value = True
        dependency = Mock(Error=RuntimeError)
        dependency.Process.return_value = self.process
        for enabled in (patch.object(watch, "psutil", dependency),
                        patch.object(watch.shutil, "which", return_value=str(node)),
                        patch.object(watch, "read_health", return_value=self.health)):
            enabled.start()
            self.addCleanup(enabled.stop)

    def test_healthy_instance_avoids_startup_and_preserves_marker(self):
        modified = self.marker.stat().st_mtime_ns
        with patch.object(watch.subprocess, "call") as fallback:
            self.assertEqual(watch.main(str(self.config), "starter", "pwsh"), 0)
            fallback.assert_not_called()
        self.assertEqual(self.marker.stat().st_mtime_ns, modified)

    def test_responding_service_with_a_different_identity_gets_full_check(self):
        for field, replacement in (("instance_id", "b" * 32), ("pid", 1234),
                                   ("provider", "other"), ("ready", False)):
            with self.subTest(field=field), patch.dict(self.health, {field: replacement}):
                self.assertFalse(watch.already_running(self.config))
        for method, replacement in (("cmdline", ["node", "other.mjs", str(self.config)]),
                                    ("cmdline", ["node", self.process.cmdline()[1], "other.json"]),
                                    ("exe", "other.exe"), ("create_time", 1), ("is_running", False)):
            with self.subTest(method=method), patch.object(self.process, method, return_value=replacement):
                self.assertFalse(watch.already_running(self.config))

    def test_missing_health_metadata_or_dependency_uses_quiet_recovery(self):
        with patch.object(watch, "psutil", None):
            self.assertFalse(watch.already_running(self.config))
        with patch.object(watch, "read_health", side_effect=ConnectionRefusedError):
            self.assertFalse(watch.already_running(self.config))
        self.marker.write_text("{")
        with patch.object(watch.subprocess, "call", return_value=23) as fallback:
            self.assertEqual(watch.main(str(self.config), "starter", "pwsh"), 23)
            args = fallback.call_args
            self.assertEqual(args.args[0][-4:], ["-File", "starter", "-ConfigPath", str(self.config)])
            self.assertEqual(args.kwargs["creationflags"], getattr(watch.subprocess, "CREATE_NO_WINDOW", 0))
