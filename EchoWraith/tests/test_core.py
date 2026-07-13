from __future__ import annotations

import io
import json
import os
import sys
import tarfile
import tempfile
import threading
import time
import types
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest import mock


TEST_DATA = tempfile.TemporaryDirectory()
os.environ["XDG_DATA_HOME"] = TEST_DATA.name

requests = types.ModuleType("requests")
requests.RequestException = type("RequestException", (Exception,), {})
requests.Session = object
requests.get = lambda *args, **kwargs: None
sys.modules.setdefault("requests", requests)

playwright = types.ModuleType("playwright")
sync_api = types.ModuleType("playwright.sync_api")
sync_api.BrowserContext = sync_api.Frame = sync_api.Locator = sync_api.Page = object
sync_api.TimeoutError = type("PlaywrightTimeoutError", (Exception,), {})
sync_api.sync_playwright = lambda: None
playwright.sync_api = sync_api
sys.modules.setdefault("playwright", playwright)
sys.modules.setdefault("playwright.sync_api", sync_api)

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "_app"))

import echowraith_core as core  # noqa: E402
import updater  # noqa: E402
import echowraith_server as server_module  # noqa: E402


class DummySink:
    def __init__(self) -> None:
        self.events = []

    def emit(self, kind, payload) -> None:
        self.events.append((kind, payload))

    def log(self, *args, **kwargs) -> None:
        pass


class DummySite:
    def __init__(self, stop_event: threading.Event, pause_event: threading.Event) -> None:
        self.stop_event = stop_event
        self.pause_event = pause_event

    def check_control(self) -> None:
        if self.stop_event.is_set():
            raise core.CancelledError("cancelled")


class EchoWraithCoreTests(unittest.TestCase):
    def test_distribution_root_has_only_launcher_and_app_folder(self) -> None:
        repository_root = ROOT.parent
        visible_entries = {path.name for path in repository_root.iterdir() if path.name != ".git"}
        self.assertEqual(visible_entries, {"BAŞLAT.bat", "EchoWraith"})
        launcher = (repository_root / "BAŞLAT.bat").read_text(encoding="utf-8")
        self.assertIn(r"EchoWraith\_app\launcher.ps1", launcher)
        self.assertTrue((ROOT / "_app" / "launcher.ps1").is_file())

    def test_recovery_event_has_a_bounded_display_lifetime(self) -> None:
        broker = core.EventBroker()
        sink = core.EventSink(broker)
        sink.recovery("Luna deniyor.", code="TEST", suggestion="Bekleyin.", ttl_ms=99_000)
        events, _ = broker.read_since(0, timeout=0)
        recovery = next(event["payload"] for event in events if event["kind"] == "recovery")
        self.assertTrue(recovery["active"])
        self.assertEqual(recovery["ttl_ms"], 15_000)

        sink.recovery("Tamamlandı.", code="DONE", suggestion="", active=False)
        events, _ = broker.read_since(events[-1]["id"], timeout=0)
        recovery = next(event["payload"] for event in events if event["kind"] == "recovery")
        self.assertFalse(recovery["active"])
        self.assertEqual(recovery["ttl_ms"], 0)

    def test_stale_transient_state_is_healed_on_startup(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            state = Path(folder) / "state.json"
            state.write_text(json.dumps({
                "settings": {"output_dir": folder},
                "lessons": [{"key": "a", "title": "Ders", "status": "Birleştiriliyor", "progress": 0.81}],
            }), encoding="utf-8")
            store = core.StateStore(state)
            self.assertEqual(store.lessons["a"].status, "Bekliyor")
            self.assertEqual(store.lessons["a"].progress, 0.0)

    def test_first_revision_forces_a_real_github_sync(self) -> None:
        with tempfile.TemporaryDirectory() as folder, mock.patch.object(updater.core, "REVISION_FILE", Path(folder) / "revision.json"), mock.patch.object(
            updater, "remote_revision", return_value={"sha": "abc123", "message": "latest", "date": "now"}
        ):
            status = updater.check_update()
            self.assertTrue(status["available"])
            self.assertEqual(status["latest"], "abc123")

    def test_update_archive_rejects_links(self) -> None:
        payload = io.BytesIO()
        with tarfile.open(fileobj=payload, mode="w:gz") as archive:
            item = tarfile.TarInfo("repo/link")
            item.type = tarfile.SYMTYPE
            item.linkname = "../../outside"
            archive.addfile(item)
        payload.seek(0)
        with tempfile.TemporaryDirectory() as folder, tarfile.open(fileobj=payload, mode="r:gz") as archive:
            with self.assertRaises(RuntimeError):
                updater._safe_extract(archive, Path(folder))

    def test_update_applies_single_folder_package_and_root_launcher(self) -> None:
        payload = io.BytesIO()
        with tarfile.open(fileobj=payload, mode="w:gz") as archive:
            files = {
                "repo/EchoWraith/_app/version.txt": b"new-app",
                "repo/EchoWraith/README.md": b"new-readme",
                "repo/BAŞLAT.bat": b"new-launcher",
            }
            for name, content in files.items():
                item = tarfile.TarInfo(name)
                item.size = len(content)
                archive.addfile(item, io.BytesIO(content))

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            install_root = root / "EchoWraith"
            (install_root / "_app").mkdir(parents=True)
            (install_root / "_app" / "version.txt").write_text("old-app", encoding="utf-8")
            (root / "BAŞLAT.bat").write_text("old-launcher", encoding="utf-8")
            with mock.patch.object(updater.core, "INSTALL_ROOT", install_root), mock.patch.object(
                updater.core, "CACHE_DIR", root / "cache"
            ), mock.patch.object(updater.core, "REVISION_FILE", root / "revision.json"), mock.patch.object(
                updater, "_download_tarball", return_value=payload.getvalue()
            ):
                result = updater.apply_update("abc123")

            self.assertTrue(result["ok"], result["error"])
            self.assertEqual((install_root / "_app" / "version.txt").read_text(encoding="utf-8"), "new-app")
            self.assertEqual((root / "BAŞLAT.bat").read_text(encoding="utf-8"), "new-launcher")

    @unittest.skipIf(os.name == "nt", "POSIX process-group assertion")
    def test_cancel_stops_external_process_group(self) -> None:
        stop = threading.Event()
        pause = threading.Event()
        pause.set()
        sink = DummySink()
        engine = core.DownloadEngine(DummySite(stop, pause), sink, stop, pause, core.Settings())
        lesson = core.Lesson(key="cancel", title="Cancel test", duration=60)
        failures = []

        def run() -> None:
            try:
                engine._run_process([
                    sys.executable,
                    "-c",
                    "import subprocess,sys,time; subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)']); print('ready', flush=True); time.sleep(60)",
                ], lesson)
            except Exception as error:  # expected cancellation
                failures.append(error)

        thread = threading.Thread(target=run)
        thread.start()
        deadline = time.time() + 5
        while engine.current_process is None and time.time() < deadline:
            time.sleep(0.02)
        engine.cancel()
        thread.join(timeout=8)
        self.assertFalse(thread.is_alive())
        self.assertTrue(any(isinstance(error, core.CancelledError) for error in failures))

    def test_encoder_probe_checks_every_supported_backend(self) -> None:
        stop = threading.Event()
        pause = threading.Event()
        pause.set()
        engine = core.DownloadEngine(DummySite(stop, pause), DummySink(), stop, pause, core.Settings())
        results = {name: engine._probe_encoder(name) for name in ("libx264", "h264_nvenc", "h264_qsv", "h264_amf")}
        self.assertTrue(results["libx264"])
        self.assertTrue(all(isinstance(value, bool) for value in results.values()))

    def test_local_http_api_settings_state_and_media_range(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            store = core.StateStore(Path(folder) / "state.json")
            store.settings.output_dir = folder
            media = Path(folder) / "sample.mp4"
            media.write_bytes(b"0123456789")
            store.lessons["media"] = core.Lesson(
                key="media", title="Media", status="Tamamlandı", output_path=str(media), progress=1.0
            )
            store.save()
            broker = core.EventBroker()
            worker = core.WorkerController(store, broker)
            httpd = server_module.EchoWraithHTTPServer((server_module.HOST, 0), server_module.EchoWraithHandler)
            previous = (server_module.STORE, server_module.BROKER, server_module.WORKER)
            server_module.STORE, server_module.BROKER, server_module.WORKER = store, broker, worker
            thread = threading.Thread(target=httpd.serve_forever, daemon=True)
            thread.start()
            base = f"http://{server_module.HOST}:{httpd.server_address[1]}"
            try:
                with urllib.request.urlopen(f"{base}/api/state", timeout=3) as response:
                    state = json.loads(response.read().decode("utf-8"))
                self.assertEqual(state["version"], core.APP_VERSION)
                self.assertEqual(state["lessons"][0]["key"], "media")

                body = json.dumps({"segment_threads": 6, "encoder": "Otomatik (en hızlı)"}).encode("utf-8")
                request = urllib.request.Request(
                    f"{base}/api/settings",
                    data=body,
                    method="PATCH",
                    headers={"Content-Type": "application/json", "Origin": base},
                )
                with urllib.request.urlopen(request, timeout=3) as response:
                    settings = json.loads(response.read().decode("utf-8"))["settings"]
                self.assertEqual(settings["segment_threads"], 6)

                request = urllib.request.Request(f"{base}/api/media/media", headers={"Range": "bytes=2-5"})
                with urllib.request.urlopen(request, timeout=3) as response:
                    self.assertEqual(response.status, 206)
                    self.assertEqual(response.read(), b"2345")
            finally:
                httpd.shutdown()
                httpd.server_close()
                thread.join(timeout=3)
                server_module.STORE, server_module.BROKER, server_module.WORKER = previous


if __name__ == "__main__":
    unittest.main(verbosity=2)
