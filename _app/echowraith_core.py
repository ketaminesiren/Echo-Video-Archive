from __future__ import annotations

import hashlib
import html
import json
import os
import queue
import random
import re
import signal
import shutil
import subprocess
import sys
import threading
import time
import traceback
import unicodedata
import webbrowser
import xml.etree.ElementTree as ET
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field, fields
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Iterable, Optional
from urllib.parse import unquote, urljoin, urlparse

import requests
from playwright.sync_api import BrowserContext, Frame, Locator, Page, TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

from diagnostics import StructuredLogger, diagnose_exception

# The old desktop interface remains only as an emergency compatibility entry
# point. The normal application imports this module without loading any GUI
# toolkit; all user-facing controls live in the web panel.
if __name__ == "__main__":
    import customtkinter as ctk
    from tkinter import filedialog, messagebox, ttk
else:
    class _LegacyCtkStub:
        CTk = object

    ctk = _LegacyCtkStub()
    filedialog = messagebox = ttk = None


APP_NAME = "EchoWraith"
APP_VERSION = "3.1.1"
APP_CREATOR = "Luna"
APP_TEAM = "Luna"
BASE_URL = "https://efsaneuzem.com"
LOGIN_URL = f"{BASE_URL}/sistemegir.php"
COURSES_URL = f"{BASE_URL}/derslerim.php"

# Statuses that only make sense while the worker thread is actively driving a
# lesson. If one is seen at rest (e.g. after a restart) it is stale.
TRANSIENT_STATUSES = frozenset({"İndiriliyor", "Birleştiriliyor", "Dönüştürülüyor", "Kaynak aranıyor"})

if os.name == "nt":
    _LOCAL_ROOT = Path(os.getenv("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    DATA_ROOT = _LOCAL_ROOT / "EchoWraith"
    LEGACY_DATA_ROOT = _LOCAL_ROOT / "EfsaneDersIndirici"
else:
    _LOCAL_ROOT = Path(os.getenv("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    DATA_ROOT = _LOCAL_ROOT / "EchoWraith"
    LEGACY_DATA_ROOT = _LOCAL_ROOT / "EfsaneDersIndirici"

PROFILE_DIR = DATA_ROOT / "browser-profile"
CACHE_DIR = DATA_ROOT / "cache"
STATE_FILE = DATA_ROOT / "state.json"
LOG_DIR = DATA_ROOT / "logs"
LOG_FILE = LOG_DIR / "echowraith.log"
SERVER_FILE = DATA_ROOT / "server.json"
WEB_ROOT = Path(__file__).resolve().parent / "web"
APP_DIR = Path(__file__).resolve().parent
INSTALL_ROOT = APP_DIR.parent
REVISION_FILE = DATA_ROOT / "revision.json"

# GitHub is treated as the source of truth for updates.
UPDATE_REPO = "ketaminesiren/echo-video-archive"
UPDATE_BRANCH = "main"


def _migrate_legacy_data() -> None:
    """Carry the previous release's session/state into EchoWraith once.

    StructuredLogger creates DATA_ROOT while it starts, so migration has to run
    before the logger is constructed.  Only missing destinations are copied;
    an existing EchoWraith profile is never overwritten.
    """

    if not LEGACY_DATA_ROOT.is_dir():
        return
    try:
        DATA_ROOT.mkdir(parents=True, exist_ok=True)
        legacy_state = LEGACY_DATA_ROOT / "state.json"
        if legacy_state.is_file() and not STATE_FILE.exists():
            shutil.copy2(legacy_state, STATE_FILE)
        legacy_profile = LEGACY_DATA_ROOT / "browser-profile"
        if legacy_profile.is_dir() and not PROFILE_DIR.exists():
            shutil.copytree(legacy_profile, PROFILE_DIR)
    except OSError:
        # A read-only or partially damaged old profile must not prevent a clean
        # start; the regular login flow will rebuild it when needed.
        pass


_migrate_legacy_data()
DIAGNOSTICS = StructuredLogger(LOG_DIR, APP_NAME, APP_VERSION)

# Kept for the legacy emergency desktop entry point. The normal launcher uses
# the web studio in studio_server.py.
PALETTE = {
    "bg": "#0b1020",
    "panel": "#111827",
    "panel_alt": "#172033",
    "border": "#263044",
    "accent": "#4f8cff",
    "accent_hover": "#3f7de9",
    "green": "#31c48d",
    "yellow": "#f5a524",
    "red": "#f97066",
    "muted": "#94a3b8",
    "text": "#f8fafc",
}


class CancelledError(RuntimeError):
    pass


def ensure_dirs() -> None:
    _migrate_legacy_data()
    for path in (DATA_ROOT, PROFILE_DIR, CACHE_DIR, LOG_DIR):
        path.mkdir(parents=True, exist_ok=True)


def now_text() -> str:
    return datetime.now().strftime("%H:%M:%S")


def safe_filename(value: str, limit: int = 145) -> str:
    value = html.unescape(value or "Ders")
    value = unicodedata.normalize("NFKC", value)
    value = re.sub(r"[<>:\"/\\|?*\x00-\x1f]", " ", value)
    value = re.sub(r"\s+", " ", value).strip(" .")
    if not value:
        value = "Ders"
    reserved = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}
    if value.upper() in reserved:
        value = f"_{value}"
    if len(value) > limit:
        digest = hashlib.sha1(value.encode("utf-8")).hexdigest()[:8]
        value = f"{value[: limit - 10].rstrip()} - {digest}"
    return value


def human_bytes(value: Optional[int]) -> str:
    if value is None or value < 0:
        return "—"
    size = float(value)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{size:.0f} {unit}" if unit in {"B", "KB"} else f"{size:.1f} {unit}"
        size /= 1024
    return "—"


def format_seconds(value: Any) -> str:
    seconds = max(0, int(float(value or 0)))
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}" if hours else f"{minutes:02d}:{secs:02d}"


def parse_size(text: str) -> Optional[int]:
    match = re.search(r"(?:download|indir)[^\n()]{0,30}\(?\s*([\d.,]+)\s*(KB|MB|GB)\s*\)?", text or "", re.I)
    if not match:
        return None
    raw_number = match.group(1)
    if "," in raw_number and "." in raw_number:
        decimal = "," if raw_number.rfind(",") > raw_number.rfind(".") else "."
        thousands = "." if decimal == "," else ","
        raw_number = raw_number.replace(thousands, "").replace(decimal, ".")
    elif "," in raw_number:
        raw_number = raw_number.replace(",", ".")
    number = float(raw_number)
    multiplier = {"KB": 1024, "MB": 1024**2, "GB": 1024**3}[match.group(2).upper()]
    return int(number * multiplier)


def lesson_key(date: str, title: str, hint: str = "") -> str:
    raw = "\x1f".join((date.strip(), title.strip(), hint.strip()))
    return hashlib.sha1(raw.encode("utf-8", "ignore")).hexdigest()[:20]


def strip_ansi(value: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", value)


def locate_bbb_cli() -> list[str]:
    local_runner = Path(__file__).with_name("bbb_runner.py")
    if local_runner.exists():
        return [sys.executable, str(local_runner)]
    candidates = [
        Path(sys.executable).with_name("bbb-dl.exe"),
        Path(sys.executable).with_name("bbb-dl"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return [str(candidate)]
    found = shutil.which("bbb-dl")
    if found:
        return [found]
    return [sys.executable, "-m", "bbb_dl"]


def get_ffmpeg_tools() -> tuple[str, str]:
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    if ffmpeg and ffprobe:
        return ffmpeg, ffprobe
    from static_ffmpeg import run

    fetched = run.get_or_fetch_platform_executables_else_raise()
    return str(fetched[0]), str(fetched[1])


@dataclass
class Lesson:
    key: str
    title: str
    date: str = ""
    href: str = ""
    locator_hint: dict[str, str] = field(default_factory=dict)
    page_number: int = 1
    selected: bool = True
    source_type: str = "Bilinmiyor"
    source_url: str = ""
    meeting_id: str = ""
    known_size: Optional[int] = None
    status: str = "Bekliyor"
    progress: float = 0.0
    output_path: str = ""
    error: str = ""
    chat_path: str = ""
    chat_json_path: str = ""
    webcam_path: str = ""
    thumbnail_path: str = ""
    transcript_path: str = ""
    transcript_json_path: str = ""
    quiz_path: str = ""
    last_position: float = 0.0
    duration: float = 0.0
    last_watched_at: str = ""
    completed: bool = False
    favorite: bool = False
    bookmarks: list[dict[str, Any]] = field(default_factory=list)
    attempts: int = 0
    bytes_downloaded: int = 0
    download_speed: float = 0.0
    eta_seconds: float = 0.0
    recovery_count: int = 0

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Lesson":
        allowed = {item.name for item in fields(cls)}
        values = {key: value for key, value in data.items() if key in allowed}
        # Earlier versions persisted signed recording URLs. They are not
        # needed for playback or retries and are discarded during migration.
        values["source_url"] = ""
        return cls(**values)


@dataclass
class Settings:
    output_dir: str = str(Path.home() / "Downloads" / "EchoWraith Dersleri")
    save_chat: bool = True
    quality: str = "Dengeli (720p)"
    encoder: str = "Otomatik (en hızlı)"
    request_delay: float = 0.8
    headless_first: bool = True
    segment_threads: int = 4
    idle_shutdown_minutes: int = 3
    transcript_model: str = "base"
    auto_thumbnail: bool = True
    auto_update: bool = True

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Settings":
        allowed = {item.name for item in fields(cls)}
        return cls(**{key: value for key, value in data.items() if key in allowed})


class StateStore:
    def __init__(self, path: Path = STATE_FILE):
        self.path = path
        self.lock = threading.RLock()
        self.settings = Settings()
        self.lessons: dict[str, Lesson] = {}
        self.profile: dict[str, Any] = {}
        self.load()

    def load(self) -> None:
        ensure_dirs()
        if not self.path.exists():
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            had_persisted_sources = any(
                isinstance(item, dict) and bool(item.get("source_url")) for item in data.get("lessons", [])
            )
            self.settings = Settings.from_dict(data.get("settings", {}))
            self.profile = data.get("profile", {}) if isinstance(data.get("profile"), dict) else {}
            self.lessons = {
                item["key"]: Lesson.from_dict(item)
                for item in data.get("lessons", [])
                if isinstance(item, dict) and item.get("key")
            }
            # No worker runs at load time, so any transient "in progress" status
            # left over from a previous session (e.g. the app was closed mid
            # "Birleştiriliyor") is stale and would otherwise stick forever with
            # no way to advance. Reconcile it against what is actually on disk.
            healed = False
            for lesson in self.lessons.values():
                if lesson.status in TRANSIENT_STATUSES:
                    if lesson.output_path and Path(lesson.output_path).is_file():
                        lesson.status = "Tamamlandı"
                        lesson.progress = 1.0
                    else:
                        lesson.status = "Bekliyor"
                        lesson.progress = 0.0
                    lesson.download_speed = 0.0
                    lesson.eta_seconds = 0.0
                    healed = True
            if had_persisted_sources or healed:
                self.save()
        except Exception:
            backup = self.path.with_suffix(f".bozuk-{int(time.time())}.json")
            try:
                shutil.copy2(self.path, backup)
            except OSError:
                pass

    def save(self) -> None:
        with self.lock:
            ensure_dirs()
            payload = {
                "version": APP_VERSION,
                "saved_at": datetime.now().isoformat(timespec="seconds"),
                "settings": asdict(self.settings),
                "profile": self.profile,
                "lessons": [{**asdict(item), "source_url": ""} for item in self.lessons.values()],
            }
            temp = self.path.with_suffix(".tmp")
            temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            temp.replace(self.path)
            try:
                self.path.chmod(0o600)
            except OSError:
                pass

    def merge_scan(self, scanned: Iterable[Lesson]) -> list[Lesson]:
        with self.lock:
            merged: dict[str, Lesson] = {}
            for new in scanned:
                old = self.lessons.get(new.key)
                if old:
                    new.selected = old.selected
                    new.source_type = old.source_type
                    new.source_url = old.source_url
                    new.meeting_id = old.meeting_id
                    new.known_size = old.known_size
                    new.status = old.status
                    new.progress = old.progress
                    new.output_path = old.output_path
                    new.error = old.error
                    new.chat_path = old.chat_path
                    new.chat_json_path = old.chat_json_path
                    new.webcam_path = old.webcam_path
                    new.thumbnail_path = old.thumbnail_path
                    new.transcript_path = old.transcript_path
                    new.transcript_json_path = old.transcript_json_path
                    new.quiz_path = old.quiz_path
                    new.last_position = old.last_position
                    new.duration = old.duration
                    new.last_watched_at = old.last_watched_at
                    new.completed = old.completed
                    new.favorite = old.favorite
                    new.bookmarks = old.bookmarks
                    new.attempts = old.attempts
                    new.bytes_downloaded = old.bytes_downloaded
                    new.download_speed = old.download_speed
                    new.eta_seconds = old.eta_seconds
                    new.recovery_count = old.recovery_count
                    if old.status == "Tamamlandı" and (not old.output_path or not Path(old.output_path).exists()):
                        new.status = "Bekliyor"
                        new.progress = 0.0
                merged[new.key] = new
            self.lessons = merged
            self.save()
            return list(self.lessons.values())


class EventBroker:
    """Thread-safe replayable event stream used by the local web panel."""

    def __init__(self, limit: int = 2000):
        self.limit = limit
        self.events: deque[dict[str, Any]] = deque(maxlen=limit)
        self.condition = threading.Condition()
        self.next_id = 1
        self.authenticated = False
        self.last_status = "Hazır"

    def put(self, item: tuple[str, Any]) -> None:
        kind, payload = item
        with self.condition:
            event = {"id": self.next_id, "kind": kind, "payload": payload}
            self.next_id += 1
            self.events.append(event)
            if kind == "auth_ok":
                self.authenticated = True
            if kind == "status":
                self.last_status = str(payload or "")
            elif kind == "job_started":
                self.last_status = str(payload or "İşlem sürüyor")
            elif kind in {"job_done", "job_cancelled"}:
                self.last_status = str(payload or "Hazır")
            elif kind == "job_error":
                self.last_status = str((payload or {}).get("message", "Hata"))
            self.condition.notify_all()

    def read_since(self, last_id: int, timeout: float = 20.0) -> tuple[list[dict[str, Any]], int]:
        deadline = time.monotonic() + timeout
        with self.condition:
            while not any(event["id"] > last_id for event in self.events):
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                self.condition.wait(remaining)
            items = [event.copy() for event in self.events if event["id"] > last_id]
            newest = items[-1]["id"] if items else max(last_id, self.next_id - 1)
            return items, newest


class EventSink:
    def __init__(self, events: Any):
        self.events = events

    def emit(self, kind: str, payload: Any = None) -> None:
        self.events.put((kind, payload))

    def log(
        self,
        message: str,
        level: str = "info",
        *,
        stage: str = "GENERAL",
        code: str = "",
        details: Any = None,
        suggestion: str = "",
        lesson_key: str = "",
        attempt: int = 0,
    ) -> dict[str, Any] | None:
        clean = strip_ansi(str(message)).strip()
        if not clean:
            return None
        payload = DIAGNOSTICS.event(
            level,
            stage,
            clean,
            code=code,
            details=details,
            suggestion=suggestion,
            lesson_key=lesson_key,
            attempt=attempt,
        )
        self.emit("log", {**payload, "time": now_text()})
        return payload

    def stage(self, stage: str, message: str, *, progress: float | None = None, lesson_key: str = "") -> None:
        payload = {"stage": stage, "message": message, "lesson_key": lesson_key}
        if progress is not None:
            payload["progress"] = max(0.0, min(1.0, float(progress)))
        self.emit("stage", payload)
        self.log(message, "info", stage=stage, lesson_key=lesson_key)

    def recovery(self, message: str, *, code: str, suggestion: str, lesson_key: str = "", active: bool = True) -> None:
        payload = {"active": active, "message": message, "code": code, "suggestion": suggestion, "lesson_key": lesson_key}
        self.emit("recovery", payload)
        self.log(message, "warning" if active else "success", stage="RECOVERY", code=code, suggestion=suggestion, lesson_key=lesson_key)

    def exception(self, stage: str, error: BaseException, *, lesson_key: str = "", attempt: int = 0) -> dict[str, Any]:
        diagnosis = diagnose_exception(error)
        payload = DIAGNOSTICS.exception(stage, error, lesson_key=lesson_key, attempt=attempt)
        self.emit("log", {**payload, "time": now_text()})
        return {**diagnosis, "log": payload}


@dataclass
class LessonView:
    page: Page
    main_page: Page
    previous_url: str
    is_new_page: bool = False
    navigated: bool = False


@dataclass
class SourceInfo:
    source_type: str
    source_url: str = ""
    meeting_id: str = ""
    size: Optional[int] = None
    chat_text: str = ""
    page_html: str = ""
    referer: str = ""


class SiteAutomation:
    def __init__(
        self,
        sink: EventSink,
        stop_event: threading.Event,
        pause_event: threading.Event,
        *,
        headless_first: bool = True,
    ):
        self.sink = sink
        self.stop_event = stop_event
        self.pause_event = pause_event
        self.headless_first = headless_first
        self.headless_active = False
        self.browser_flavor = ""
        self.playwright = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.recent_urls: list[str] = []

    def check_control(self) -> None:
        if self.stop_event.is_set():
            raise CancelledError("İşlem kullanıcı tarafından durduruldu.")
        while not self.pause_event.wait(0.25):
            if self.stop_event.is_set():
                raise CancelledError("İşlem kullanıcı tarafından durduruldu.")

    def __enter__(self) -> "SiteAutomation":
        ensure_dirs()
        self.playwright = sync_playwright().start()
        self.sink.stage("BROWSER", "Arka plan oturumu hazırlanıyor…", progress=0.05)
        base_args = dict(
            user_data_dir=str(PROFILE_DIR),
            accept_downloads=True,
            viewport={"width": 1420, "height": 900},
            locale="tr-TR",
            downloads_path=str(CACHE_DIR / "browser-downloads"),
            args=["--disable-background-networking", "--disable-component-update", "--disable-default-apps"],
        )
        force = os.getenv("ECHOWRAITH_HEADLESS", "").strip()
        prefer_headless = force != "0" and (force == "1" or self.headless_first)
        plans = [(prefer_headless, "chrome"), (prefer_headless, "bundled")]
        if prefer_headless:
            plans.extend([(False, "chrome"), (False, "bundled")])
        errors: list[str] = []
        for headless, flavor in plans:
            try:
                args = {**base_args, "headless": headless}
                if flavor == "chrome":
                    args["channel"] = "chrome"
                self.context = self.playwright.chromium.launch_persistent_context(**args)
                self.headless_active = headless
                self.browser_flavor = flavor
                if not headless:
                    self.sink.recovery(
                        "Arka plan modu yeterli olmadı; güvenli görünür tarayıcı yöntemi açıldı.",
                        code="VISIBLE_BROWSER_FALLBACK",
                        suggestion="Açılan pencere işlem bitince otomatik kapanacaktır.",
                    )
                break
            except Exception as error:
                errors.append(f"{flavor}/{'headless' if headless else 'visible'}: {error}")
        if self.context is None:
            raise RuntimeError("Tarayıcı motoru başlatılamadı. " + " | ".join(errors[-3:]))
        self.context.set_default_timeout(15_000)
        self.context.set_default_navigation_timeout(45_000)
        self.context.on("request", self._capture_request)
        self.page = self.context.pages[0] if self.context.pages else self.context.new_page()
        self.sink.log(
            f"Tarayıcı hazır: {self.browser_flavor}, {'arka plan' if self.headless_active else 'görünür'} mod.",
            "success",
            stage="BROWSER",
            code="BROWSER_READY",
        )
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        try:
            if self.context:
                self.context.close()
        finally:
            if self.playwright:
                self.playwright.stop()
            self.context = None
            self.page = None
            self.playwright = None

    def restart_visible(self) -> None:
        if not self.headless_active:
            return
        self.sink.recovery(
            "Site arka plan modunda tamamlanamadı; görünür yöntem deneniyor. Lütfen bekleyin.",
            code="HEADLESS_RETRY_VISIBLE",
            suggestion="Gerekirse açılan pencerede yalnızca giriş işlemini tamamlayın.",
        )
        if self.context:
            self.context.close()
        if self.playwright:
            self.playwright.stop()
        self.context = None
        self.page = None
        self.playwright = sync_playwright().start()
        args = dict(
            user_data_dir=str(PROFILE_DIR),
            headless=False,
            accept_downloads=True,
            viewport={"width": 1420, "height": 900},
            locale="tr-TR",
            downloads_path=str(CACHE_DIR / "browser-downloads"),
        )
        try:
            self.context = self.playwright.chromium.launch_persistent_context(channel="chrome", **args)
            self.browser_flavor = "chrome"
        except Exception:
            self.context = self.playwright.chromium.launch_persistent_context(**args)
            self.browser_flavor = "bundled"
        self.headless_active = False
        self.context.set_default_timeout(15_000)
        self.context.set_default_navigation_timeout(45_000)
        self.context.on("request", self._capture_request)
        self.page = self.context.pages[0] if self.context.pages else self.context.new_page()

    def _capture_request(self, request) -> None:
        url = request.url
        low = url.lower()
        if any(token in low for token in ("zoom.us", "/presentation/", ".mp4", ".m4v", ".webm", ".m3u8", ".mpd", "manifest", "vimeo.com", "youtube.com", "youtu.be", "slides_new.xml")):
            self.recent_urls.append(url)
            if len(self.recent_urls) > 1500:
                del self.recent_urls[:500]

    @staticmethod
    def _is_logged_in(page: Page) -> bool:
        url = page.url.lower()
        if "sistemegir.php" in url:
            return False
        text = ""
        try:
            text = page.locator("body").inner_text(timeout=3_000).lower()
        except Exception:
            pass
        return "derslerim" in text or "öğrenci sayfam" in text or "çıkış" in text

    def ensure_login(self, email: str = "", password: str = "") -> None:
        assert self.page is not None
        self.check_control()
        self.sink.emit("status", "Oturum kontrol ediliyor…")
        try:
            self.page.goto(COURSES_URL, wait_until="domcontentloaded")
        except PlaywrightTimeoutError:
            pass
        if self._is_logged_in(self.page):
            self.sink.log("Kayıtlı tarayıcı oturumu kullanıldı.", "success")
            self.sink.emit("auth_ok")
            return

        self.page.goto(LOGIN_URL, wait_until="domcontentloaded")
        if email and password:
            password_box = self._first_visible(
                self.page,
                ["input[type='password']", "input[name*='sifre' i]", "input[name*='password' i]"],
            )
            email_box: Optional[Locator] = None
            form: Optional[Locator] = None
            if password_box:
                form = password_box.locator("xpath=ancestor::form[1]")
                for selector in (
                    "input[type='email']",
                    "input[name*='mail' i]",
                    "input[placeholder*='mail' i]",
                    "input[type='text']",
                ):
                    candidates = form.locator(selector)
                    for index in range(candidates.count()):
                        candidate = candidates.nth(index)
                        if candidate.is_visible():
                            email_box = candidate
                            break
                    if email_box:
                        break
            if email_box and password_box and form:
                email_box.fill(email)
                password_box.fill(password)
                submit = form.locator("button[type='submit'], input[type='submit']")
                if not submit.count():
                    submit = form.locator("button, input[type='button']").filter(has_text=re.compile(r"giriş|login", re.I))
                clicked = False
                for index in range(submit.count()):
                    candidate = submit.nth(index)
                    if candidate.is_visible():
                        candidate.click()
                        clicked = True
                        break
                if not clicked:
                    password_box.press("Enter")
                try:
                    self.page.wait_for_load_state("domcontentloaded", timeout=20_000)
                except PlaywrightTimeoutError:
                    pass
                deadline = time.time() + 20
                while time.time() < deadline:
                    self.check_control()
                    if self._is_logged_in(self.page):
                        self.sink.log("Giriş başarılı. Şifre diske kaydedilmedi.", "success")
                        self.sink.emit("auth_ok")
                        return
                    time.sleep(0.5)

        if self.headless_active:
            self.restart_visible()
            return self.ensure_login(email, password)

        self.sink.emit("needs_login")
        self.sink.log("Tarayıcıda öğrenci girişini tamamlamanı bekliyorum (en fazla 3 dakika).", "warning")
        deadline = time.time() + 180
        while time.time() < deadline:
            self.check_control()
            if self._is_logged_in(self.page):
                self.sink.log("Tarayıcı girişi algılandı; oturum bundan sonra yeniden kullanılacak.", "success")
                self.sink.emit("auth_ok")
                return
            time.sleep(1)
        raise RuntimeError("Giriş tamamlanmadı. E-posta/şifreyi kontrol edip tekrar dene.")

    @staticmethod
    def _first_visible(page: Page, selectors: list[str]) -> Optional[Locator]:
        for selector in selectors:
            locator = page.locator(selector)
            for index in range(min(locator.count(), 8)):
                candidate = locator.nth(index)
                try:
                    if candidate.is_visible():
                        return candidate
                except Exception:
                    continue
        return None

    def extract_profile(self) -> dict[str, Any]:
        """Collect user-visible membership information without secrets."""
        assert self.page is not None and self.context is not None
        self.sink.stage("PROFILE", "Üyelik bilgileri güncelleniyor…", progress=0.12)
        try:
            if "derslerim" not in self.page.url.lower():
                self.page.goto(COURSES_URL, wait_until="domcontentloaded")
        except PlaywrightTimeoutError:
            pass

        display_name = ""
        try:
            candidates = self.page.locator("header a, header button, nav a, .menu a, .dropdown-toggle")
            for index in range(min(candidates.count(), 80)):
                text = re.sub(r"\s+", " ", candidates.nth(index).inner_text(timeout=700)).strip()
                low = text.casefold()
                if text and 2 <= len(text.split()) <= 5 and not any(token in low for token in ("ana sayfa", "video", "ders", "çıkış", "menü")):
                    if text.isupper() or "öğrenci" in low:
                        display_name = text.title()
                        break
        except Exception:
            pass

        profile_url = ""
        try:
            links = self.page.locator("a")
            for index in range(min(links.count(), 250)):
                item = links.nth(index)
                label = re.sub(r"\s+", " ", item.inner_text(timeout=500)).strip()
                href = item.get_attribute("href") or ""
                joined = f"{label} {href}".casefold()
                if any(token in joined for token in ("bilgilerim", "profilim", "hesabım", "hesabim", "uyebilgi", "üyelik bilgiler")):
                    profile_url = href
                    break
        except Exception:
            pass

        target = self.context.new_page()
        fields_found: list[dict[str, str]] = []
        packages: list[str] = []
        try:
            if profile_url:
                target.goto(urljoin(f"{BASE_URL}/", profile_url), wait_until="domcontentloaded")
            else:
                target.goto(f"{BASE_URL}/bilgilerim.php", wait_until="domcontentloaded")
            if not self._is_logged_in(target):
                raise RuntimeError("Profil sayfası oturumu doğrulamadı.")
            raw = target.evaluate(
                r"""
                () => {
                  const clean = value => String(value || '').replace(/\s+/g, ' ').trim();
                  const fields = [];
                  for (const input of document.querySelectorAll('input, select, textarea')) {
                    const type = (input.getAttribute('type') || '').toLowerCase();
                    if (['password','hidden','submit','button'].includes(type)) continue;
                    const id = input.id;
                    const label = clean((id && document.querySelector(`label[for="${CSS.escape(id)}"]`)?.innerText) || input.closest('label')?.innerText || input.getAttribute('placeholder') || input.getAttribute('name'));
                    const value = clean(input.tagName === 'SELECT' ? input.selectedOptions?.[0]?.textContent : input.value);
                    if (label && value) fields.push({label, value});
                  }
                  const rows = [...document.querySelectorAll('table tr, .list-group-item, .profile-info li, dl')]
                    .map(el => clean(el.innerText)).filter(text => text && text.length < 300);
                  const bodyLines = String(document.body?.innerText || '').split(/\n+/).map(clean).filter(Boolean);
                  return {fields, rows: [...new Set(rows)].slice(0, 60), lines: bodyLines.slice(0, 250), title: document.title};
                }
                """
            )
            blocked = ("şifre", "sifre", "password", "token", "kimlik", "t.c", "tc no", "adres")
            seen: set[str] = set()
            for item in raw.get("fields", []):
                label = re.sub(r"\s+", " ", str(item.get("label", ""))).strip(" :*")[:80]
                value = re.sub(r"\s+", " ", str(item.get("value", ""))).strip()[:180]
                low = label.casefold()
                if not label or not value or any(token in low for token in blocked):
                    continue
                marker = f"{low}\x1f{value.casefold()}"
                if marker not in seen:
                    fields_found.append({"label": label, "value": value})
                    seen.add(marker)
                if not display_name and any(token in low for token in ("ad soyad", "adı soyadı", "isim")):
                    display_name = value
            package_pattern = re.compile(r"(?:paket|eğitim|kamp|üyelik).{0,160}", re.I)
            for line in [*raw.get("rows", []), *raw.get("lines", [])]:
                text = re.sub(r"\s+", " ", str(line)).strip()
                if package_pattern.search(text) and 8 <= len(text) <= 220 and text.casefold() not in {item.casefold() for item in packages}:
                    packages.append(text)
                    if len(packages) >= 12:
                        break
        except Exception as error:
            self.sink.log(
                "Profil ayrıntıları tam okunamadı; temel hesap bilgileri kullanılacak.",
                "warning",
                stage="PROFILE",
                code="PROFILE_PARTIAL",
                details=str(error),
                suggestion="Ders taraması etkilenmeden devam eder.",
            )
        finally:
            try:
                target.close()
            except Exception:
                pass

        profile = {
            "display_name": display_name or "Öğrenci Hesabı",
            "fields": fields_found[:24],
            "packages": packages,
            "updated_at": datetime.now().isoformat(timespec="seconds"),
            "source": "Efsane Uzem",
        }
        self.sink.emit("profile_update", profile)
        self.sink.log("Üyelik bilgileri güncellendi.", "success", stage="PROFILE", code="PROFILE_READY")
        return profile

    def _find_course_table(self) -> Locator:
        assert self.page is not None
        tables = self.page.locator("table")
        best: Optional[Locator] = None
        best_score = -1
        for index in range(tables.count()):
            table = tables.nth(index)
            try:
                text = table.inner_text(timeout=2_000).lower()
                rows = table.locator("tbody tr").count()
            except Exception:
                continue
            score = rows + (100 if "video derslerim" in text else 0) + (30 if "tarih" in text else 0)
            if score > best_score:
                best, best_score = table, score
        if best is None:
            raise RuntimeError("Ders tablosu bulunamadı. Site görünümü değişmiş olabilir.")
        return best

    def _maximize_page_length(self) -> None:
        assert self.page is not None
        selects = self.page.locator(".dataTables_length select, select[name$='_length'], select[aria-controls]")
        for index in range(selects.count()):
            select = selects.nth(index)
            try:
                parent_text = select.locator("xpath=..").inner_text(timeout=1_000).lower()
                name = (select.get_attribute("name") or "").lower()
                is_length_control = (
                    "kayıt" in parent_text
                    or "entries" in parent_text
                    or name.endswith("_length")
                    or select.get_attribute("aria-controls") is not None
                )
                if not is_length_control:
                    continue
            except Exception:
                continue
            try:
                options = select.locator("option").evaluate_all(
                    "els => els.map(o => ({value:o.value, text:(o.textContent||'').trim()}))"
                )
            except Exception:
                continue
            if not options:
                continue
            numeric = []
            for option in options:
                text = f"{option.get('value', '')} {option.get('text', '')}".lower()
                if option.get("value") == "-1" or "tümü" in text or "all" in text:
                    numeric.append((10**9, option["value"]))
                else:
                    found = re.search(r"\d+", option.get("text", ""))
                    if found:
                        numeric.append((int(found.group()), option["value"]))
            if len(numeric) >= 2:
                choice = max(numeric)[1]
                try:
                    select.select_option(choice)
                    self.page.wait_for_timeout(900)
                    return
                except Exception:
                    pass

    @staticmethod
    def _rows_from_table(table: Locator) -> list[dict[str, Any]]:
        return table.locator("tbody tr").evaluate_all(
            """
            rows => rows.map((tr, rowIndex) => {
              const cells = [...tr.querySelectorAll('td')];
              const links = [...tr.querySelectorAll('a')].map(a => ({
                text: (a.innerText || a.textContent || '').replace(/\\s+/g,' ').trim(),
                href: a.href || '',
                onclick: a.getAttribute('onclick') || '',
                attrs: Object.fromEntries([...a.attributes].map(x => [x.name, x.value]))
              }));
              const useful = links.filter(x => x.text).sort((a,b) => b.text.length-a.text.length)[0] || links[0] || {};
              return {
                rowIndex,
                text: (tr.innerText || '').replace(/\\s+/g,' ').trim(),
                cells: cells.map(td => (td.innerText || td.textContent || '').replace(/\\s+/g,' ').trim()),
                title: useful.text || (cells.at(-1)?.innerText || '').replace(/\\s+/g,' ').trim(),
                href: useful.href || '',
                onclick: useful.onclick || '',
                attrs: useful.attrs || {},
                rowAttrs: Object.fromEntries([...tr.attributes].map(x => [x.name, x.value]))
              };
            }).filter(x => x.title && !/kayıt bulunamadı|no data/i.test(x.text))
            """
        )

    def scan_lessons(self) -> list[Lesson]:
        assert self.page is not None
        self.page.goto(COURSES_URL, wait_until="domcontentloaded")
        self.page.wait_for_timeout(700)
        self._maximize_page_length()
        scanned: list[Lesson] = []
        seen_fingerprints: set[str] = set()
        occurrence: dict[str, int] = {}
        page_number = 1

        while True:
            self.check_control()
            table = self._find_course_table()
            rows = self._rows_from_table(table)
            fingerprint = hashlib.sha1("|".join(row.get("text", "") for row in rows).encode("utf-8")).hexdigest()
            if fingerprint in seen_fingerprints:
                break
            seen_fingerprints.add(fingerprint)

            for row in rows:
                title = re.sub(r"\s+", " ", row.get("title", "")).strip()
                date_match = re.search(r"\b\d{2}\.\d{2}\.\d{4}\b", row.get("text", ""))
                date = date_match.group(0) if date_match else (row.get("cells") or [""])[0]
                hint_data = {
                    "onclick": row.get("onclick", ""),
                    **{str(k): str(v) for k, v in (row.get("attrs") or {}).items()},
                    **{f"row:{k}": str(v) for k, v in (row.get("rowAttrs") or {}).items()},
                }
                hint = json.dumps(hint_data, sort_keys=True, ensure_ascii=False)
                base_key = lesson_key(date, title, f"{row.get('href','')}|{hint}")
                occurrence[base_key] = occurrence.get(base_key, 0) + 1
                key = base_key if occurrence[base_key] == 1 else lesson_key(date, title, f"{hint}|{occurrence[base_key]}")
                scanned.append(
                    Lesson(
                        key=key,
                        title=title,
                        date=date,
                        href=row.get("href", ""),
                        locator_hint=hint_data,
                        page_number=page_number,
                    )
                )

            self.sink.emit("scan_progress", {"page": page_number, "count": len(scanned)})
            self.sink.log(f"{page_number}. tablo sayfası tarandı; toplam {len(scanned)} ders bulundu.")
            next_button = self._find_next_button()
            if not next_button:
                break
            first_before = rows[0].get("text", "") if rows else ""
            try:
                next_button.click()
                self.page.wait_for_function(
                    """before => {
                      const row = document.querySelector('table tbody tr');
                      return row && (row.innerText || '').trim() !== before;
                    }""",
                    arg=first_before,
                    timeout=12_000,
                )
            except Exception:
                self.page.wait_for_timeout(900)
            page_number += 1

        if not scanned:
            raise RuntimeError("Hiç ders bulunamadı. Paket erişiminin açık olduğunu kontrol et.")
        return scanned

    def _find_next_button(self) -> Optional[Locator]:
        assert self.page is not None
        candidates = self.page.locator("a, button").filter(has_text=re.compile(r"^\s*(Sonraki|Next)\s*$", re.I))
        for index in range(candidates.count() - 1, -1, -1):
            item = candidates.nth(index)
            try:
                if not item.is_visible():
                    continue
                disabled = item.get_attribute("disabled") is not None or item.get_attribute("aria-disabled") == "true"
                cls = (item.get_attribute("class") or "") + " " + (item.locator("xpath=..").get_attribute("class") or "")
                if disabled or "disabled" in cls.lower():
                    continue
                return item
            except Exception:
                continue
        return None

    def _locate_lesson_row(self, lesson: Lesson) -> Locator:
        assert self.page is not None
        self.page.goto(COURSES_URL, wait_until="domcontentloaded")
        self.page.wait_for_timeout(500)
        search_boxes = self.page.locator("input[type='search'], .dataTables_filter input, input[aria-controls]")
        search = None
        for index in range(search_boxes.count()):
            candidate = search_boxes.nth(index)
            if candidate.is_visible():
                search = candidate
                break
        if search:
            query = re.sub(r"\([^)]*dk\.?\s*\)", "", lesson.title, flags=re.I).strip()
            search.fill(query[:100])
            self.page.wait_for_timeout(900)
        table = self._find_course_table()
        rows = table.locator("tbody tr")
        best: Optional[Locator] = None
        for index in range(rows.count()):
            row = rows.nth(index)
            try:
                text = re.sub(r"\s+", " ", row.inner_text()).strip()
            except Exception:
                continue
            if lesson.title in text and (not lesson.date or lesson.date in text):
                return row
            if lesson.title[:45].lower() in text.lower():
                best = row
        if best:
            return best
        raise RuntimeError(f"Ders satırı yeniden bulunamadı: {lesson.title}")

    def open_lesson(self, lesson: Lesson) -> LessonView:
        assert self.page is not None and self.context is not None
        self.check_control()
        row = self._locate_lesson_row(lesson)
        links = row.locator("a")
        link: Optional[Locator] = None
        best_length = -1
        for index in range(links.count()):
            candidate = links.nth(index)
            try:
                text = candidate.inner_text().strip()
            except Exception:
                text = ""
            if len(text) > best_length:
                link, best_length = candidate, len(text)
        if link is None:
            raise RuntimeError("Ders bağlantısı bulunamadı.")

        previous_url = self.page.url
        new_pages: list[Page] = []

        def handler(opened: Page) -> None:
            new_pages.append(opened)

        self.context.on("page", handler)
        self.recent_urls.clear()
        try:
            link.click()
            self.page.wait_for_timeout(1600)
        finally:
            self.context.remove_listener("page", handler)

        if new_pages:
            target = new_pages[-1]
            try:
                target.wait_for_load_state("domcontentloaded", timeout=30_000)
            except PlaywrightTimeoutError:
                pass
            return LessonView(target, self.page, previous_url, is_new_page=True, navigated=True)

        navigated = self.page.url != previous_url
        return LessonView(self.page, self.page, previous_url, is_new_page=False, navigated=navigated)

    def close_lesson(self, view: LessonView) -> None:
        if view.is_new_page:
            try:
                view.page.close()
            except Exception:
                pass
            return
        if view.navigated:
            try:
                view.page.goto(COURSES_URL, wait_until="domcontentloaded")
            except Exception:
                pass
            return
        try:
            view.page.keyboard.press("Escape")
            view.page.wait_for_timeout(350)
        except Exception:
            pass
        selectors = ".mfp-close, .fancybox-close, .fancybox-button--close, [data-dismiss='modal'], button[aria-label*='close' i], button[aria-label*='kapat' i]"
        candidates = view.page.locator(selectors)
        for index in range(candidates.count() - 1, -1, -1):
            try:
                if candidates.nth(index).is_visible():
                    candidates.nth(index).click()
                    break
            except Exception:
                continue

    def accept_cookies(self, page: Page) -> None:
        patterns = re.compile(r"accept cookies|accept all|tüm.*kabul|çerez.*kabul", re.I)
        for frame in list(page.frames):
            try:
                buttons = frame.locator("button, [role='button'], input[type='button']")
                for index in range(min(buttons.count(), 40)):
                    button = buttons.nth(index)
                    label = (button.inner_text(timeout=500) or button.get_attribute("value") or "").strip()
                    if patterns.search(label) and button.is_visible():
                        button.click()
                        frame.wait_for_timeout(700)
                        break
            except Exception:
                continue

    @staticmethod
    def _snapshot_frame(frame: Frame) -> dict[str, Any]:
        return frame.evaluate(
            r"""
            () => {
              const abs = v => { try { return new URL(v, location.href).href } catch { return v || '' } };
              const links = [...document.querySelectorAll('a')].map(a => ({
                text:(a.innerText||a.textContent||'').replace(/\s+/g,' ').trim(),
                href:abs(a.getAttribute('href')||'')
              }));
              const media = [...document.querySelectorAll('video,audio,source,iframe')].map(el => ({
                tag:el.tagName.toLowerCase(),
                src:abs(el.currentSrc || el.getAttribute('src') || ''),
                type:el.getAttribute('type') || ''
              }));
              const special = [];
              for (const el of document.querySelectorAll('*')) {
                for (const attr of el.attributes || []) {
                  if (/timeline|source|download|recording|meeting|playback/i.test(attr.name) ||
                      /slides_new\.xml|\/presentation\/|zoom\.us|\.m3u8|\.mpd|\.mp4|\.m4v|\.webm|vimeo\.com|youtube\.com|youtu\.be/i.test(attr.value)) {
                    special.push({name:attr.name, value:abs(attr.value)});
                  }
                }
              }
              const chats = [...document.querySelectorAll('#chat-area,[class*="chat" i],[aria-label*="chat" i]')]
                .map(el => (el.innerText||'').trim()).filter(Boolean);
              return {
                url:location.href,
                title:document.title || '',
                text:(document.body?.innerText || '').slice(0,150000),
                links,
                media,
                special:special.slice(0,2000),
                chats:[...new Set(chats)].slice(0,20),
                hasAcorn:!!document.querySelector('.acorn-player,#chat-area,[data-timeline-sources]')
              };
            }
            """
        )

    def inspect_source(self, view: LessonView) -> SourceInfo:
        page = view.page
        snapshots: list[dict[str, Any]] = []
        for attempt in range(6):
            self.check_control()
            self.accept_cookies(page)
            snapshots = []
            for frame in list(page.frames):
                try:
                    snapshots.append(self._snapshot_frame(frame))
                except Exception:
                    continue
            serialized = json.dumps(snapshots, ensure_ascii=False).lower()
            if any(token in serialized for token in ("zoom.us", "slides_new.xml", "data-timeline", ".mp4", ".m4v", ".webm", ".m3u8", ".mpd", "vimeo.com", "youtube.com", "download")):
                break
            if attempt < 5:
                page.wait_for_timeout(1000)

        all_urls: list[str] = list(self.recent_urls)
        all_text: list[str] = []
        chat_chunks: list[str] = []
        download_links: list[tuple[str, str]] = []
        media_urls: list[str] = []
        has_acorn = False
        for snap in snapshots:
            all_urls.append(snap.get("url", ""))
            all_text.append(snap.get("text", ""))
            has_acorn = has_acorn or bool(snap.get("hasAcorn"))
            chat_chunks.extend(snap.get("chats", []))
            for link in snap.get("links", []):
                href = link.get("href", "")
                label = link.get("text", "")
                all_urls.append(href)
                if re.search(r"download|indir", label, re.I):
                    download_links.append((href, label))
            for media in snap.get("media", []):
                source = media.get("src", "")
                if source:
                    media_urls.append(source)
                    all_urls.append(source)
            for item in snap.get("special", []):
                value = item.get("value", "")
                if value:
                    all_urls.append(value)

        all_urls = [unquote(url) for url in dict.fromkeys(url for url in all_urls if url and not url.startswith("blob:"))]
        joined_text = "\n".join(all_text)
        chat_text = "\n\n".join(dict.fromkeys(chunk for chunk in chat_chunks if len(chunk) > 3))
        size = parse_size(joined_text)

        timeline_urls = [url for url in all_urls if "slides_new.xml" in url.lower() or re.search(r"/presentation/[^/]+/(?:metadata|shapes|events)\.(?:xml|svg)", url, re.I)]
        meeting_id = ""
        for url in timeline_urls + all_urls:
            match = re.search(r"/presentation/([0-9a-f]+-\d+)(?:/|$)", url, re.I)
            if match:
                meeting_id = match.group(1)
                break
        if meeting_id or has_acorn:
            if not meeting_id:
                match = re.search(r"presentation/([0-9a-f]+-\d+)/", joined_text, re.I)
                meeting_id = match.group(1) if match else ""
            if meeting_id:
                origin = BASE_URL
                for url in timeline_urls:
                    parsed = urlparse(url)
                    if parsed.scheme and parsed.netloc:
                        origin = f"{parsed.scheme}://{parsed.netloc}"
                        break
                playback = f"{origin}/playback/presentation/2.3/playback.html?meetingId={meeting_id}"
                try:
                    page_html = page.content()
                except Exception:
                    page_html = ""
                return SourceInfo("BBB / TUES", playback, meeting_id, size, chat_text, page_html, page.url)

        zoom_urls = [url for url in all_urls if "zoom.us" in urlparse(url).netloc.lower()]
        if zoom_urls:
            direct = ""
            for href, _label in download_links:
                if "zoom.us" in urlparse(href).netloc.lower() or re.search(r"download|\.mp4", href, re.I):
                    direct = href
                    break
            if not direct:
                direct = next((url for url in zoom_urls if re.search(r"download|\.mp4", url, re.I)), zoom_urls[0])
            return SourceInfo("Zoom", direct, size=size, chat_text=chat_text, referer=page.url)

        direct_links = [href for href, _ in download_links if href.startswith("http")]
        platform_urls = [
            url for url in all_urls
            if any(host in (urlparse(url).netloc or "").lower() for host in ("youtube.com", "youtu.be", "vimeo.com"))
        ]
        if platform_urls:
            return SourceInfo("Harici video", platform_urls[0], size=size, chat_text=chat_text, referer=page.url)

        direct_media = [url for url in media_urls + all_urls if re.search(r"\.(?:mp4|m4v|webm|m3u8|mpd)(?:[?#]|$)", url, re.I)]
        if direct_links or direct_media:
            source = (direct_links + direct_media)[0]
            kind = "HLS" if ".m3u8" in source.lower() else "DASH" if ".mpd" in source.lower() else "Doğrudan video"
            return SourceInfo(kind, source, size=size, chat_text=chat_text, referer=page.url)

        raise RuntimeError("Bu dersin medya kaynağı tanınamadı. Oynatıcı yüklenmemiş veya kayıt erişimi kapanmış olabilir.")

    def cookies(self) -> list[dict[str, Any]]:
        assert self.context is not None
        return self.context.cookies()

    def user_agent(self) -> str:
        assert self.page is not None
        try:
            return self.page.evaluate("navigator.userAgent")
        except Exception:
            return "Mozilla/5.0"

    def click_download_fallback(self, page: Page, target: Path) -> None:
        self.accept_cookies(page)
        for frame in list(page.frames):
            try:
                links = frame.locator("a,button").filter(has_text=re.compile(r"download|indir", re.I))
                for index in range(links.count()):
                    item = links.nth(index)
                    if not item.is_visible():
                        continue
                    try:
                        with page.expect_download(timeout=120_000) as pending:
                            item.click()
                        download = pending.value
                        target.parent.mkdir(parents=True, exist_ok=True)
                        download.save_as(str(target))
                        return
                    except PlaywrightTimeoutError:
                        continue
            except Exception:
                continue
        raise RuntimeError("Tarayıcıdaki Download bağlantısı dosya indirmesi başlatmadı.")


class DownloadEngine:
    def __init__(
        self,
        site: SiteAutomation,
        sink: EventSink,
        stop_event: threading.Event,
        pause_event: threading.Event,
        settings: Settings,
    ):
        self.site = site
        self.sink = sink
        self.stop_event = stop_event
        self.pause_event = pause_event
        self.settings = settings
        self.ffmpeg: Optional[str] = None
        self.ffprobe: Optional[str] = None
        self.current_process: Optional[subprocess.Popen[str]] = None
        self._process_lock = threading.RLock()
        self._encoder_cache: dict[str, bool] = {}

    def check_control(self) -> None:
        self.site.check_control()

    def ensure_tools(self) -> None:
        if self.ffmpeg and self.ffprobe:
            return
        self.sink.emit("status", "FFmpeg hazırlanıyor…")
        self.ffmpeg, self.ffprobe = get_ffmpeg_tools()
        self.sink.log("FFmpeg ve FFprobe hazır.", "success")

    @staticmethod
    def _requests_session(cookies: list[dict[str, Any]]) -> requests.Session:
        session = requests.Session()
        try:
            from requests.adapters import HTTPAdapter
            from urllib3.util.retry import Retry

            retry = Retry(
                total=4,
                connect=4,
                read=3,
                status=4,
                backoff_factor=0.7,
                status_forcelist=(429, 500, 502, 503, 504),
                allowed_methods=frozenset({"GET", "HEAD"}),
                respect_retry_after_header=True,
            )
            adapter = HTTPAdapter(max_retries=retry, pool_connections=10, pool_maxsize=10)
            session.mount("https://", adapter)
            session.mount("http://", adapter)
        except (ImportError, AttributeError):
            # requests still works without the optional retry adapter; the
            # outer lesson recovery loop remains available.
            pass
        for cookie in cookies:
            try:
                session.cookies.set(
                    cookie["name"],
                    cookie["value"],
                    domain=cookie.get("domain"),
                    path=cookie.get("path", "/"),
                )
            except Exception:
                continue
        return session

    @staticmethod
    def _cookie_header(cookies: list[dict[str, Any]], url: str = "") -> str:
        host = urlparse(url).hostname or ""
        pairs = []
        for cookie in cookies:
            domain = (cookie.get("domain") or "").lstrip(".")
            if not host or not domain or host == domain or host.endswith(f".{domain}"):
                pairs.append(f"{cookie.get('name')}={cookie.get('value')}")
        return "; ".join(pairs)

    @staticmethod
    def write_netscape_cookies(path: Path, cookies: list[dict[str, Any]]) -> None:
        lines = ["# Netscape HTTP Cookie File", "# Generated locally by EchoWraith", ""]
        for cookie in cookies:
            domain = cookie.get("domain") or urlparse(BASE_URL).hostname or ""
            include_subdomains = "TRUE" if domain.startswith(".") else "FALSE"
            cookie_path = cookie.get("path") or "/"
            secure = "TRUE" if cookie.get("secure") else "FALSE"
            expires = int(cookie.get("expires") or 0)
            if expires < 0:
                expires = 0
            name = str(cookie.get("name", "")).replace("\t", "")
            value = str(cookie.get("value", "")).replace("\t", "")
            lines.append("\t".join((domain, include_subdomains, cookie_path, secure, str(expires), name, value)))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        try:
            path.chmod(0o600)
        except OSError:
            pass

    def target_for(self, lesson: Lesson) -> Path:
        root = Path(self.settings.output_dir).expanduser()
        root.mkdir(parents=True, exist_ok=True)
        prefix = f"{lesson.date} - " if lesson.date else ""
        return root / f"{safe_filename(prefix + lesson.title)}.mp4"

    def download_direct(
        self,
        source_url: str,
        target: Path,
        cookies: list[dict[str, Any]],
        user_agent: str,
        referer: str,
        lesson: Lesson,
    ) -> None:
        part = target.with_suffix(target.suffix + ".part")
        base_headers = {"User-Agent": user_agent, "Accept": "*/*", "Referer": referer or BASE_URL}
        target.parent.mkdir(parents=True, exist_ok=True)
        session = self._requests_session(cookies)
        total = int(lesson.known_size or 0)
        supports_ranges = False
        try:
            with session.get(
                source_url,
                headers={**base_headers, "Range": "bytes=0-0"},
                stream=True,
                allow_redirects=True,
                timeout=(20, 45),
            ) as probe:
                content_type = (probe.headers.get("content-type") or "").lower()
                if "text/html" in content_type:
                    raise RuntimeError("Download bağlantısı video yerine giriş/HTML sayfası döndürdü.")
                range_match = re.search(r"/(\d+)$", probe.headers.get("content-range", ""))
                if range_match:
                    total = int(range_match.group(1))
                elif not total and (probe.headers.get("content-length") or "").isdigit():
                    total = int(probe.headers["content-length"])
                supports_ranges = probe.status_code == 206 and total > 1
        except RuntimeError:
            raise
        except Exception as error:
            self.sink.log(
                "Sunucu boyut sorgusuna yanıt vermedi; güvenli akış indirmesine geçiliyor.",
                "warning",
                stage="DOWNLOAD",
                code="PROBE_FALLBACK",
                details=str(error),
                lesson_key=lesson.key,
            )

        threads = max(1, min(int(getattr(self.settings, "segment_threads", 4) or 1), 8))
        if supports_ranges and total >= 16 * 1024 * 1024 and threads > 1 and not part.exists():
            try:
                self._download_segmented(source_url, part, cookies, base_headers, lesson, total, threads)
                part.replace(target)
                return
            except CancelledError:
                raise
            except Exception as error:
                lesson.recovery_count += 1
                self.sink.recovery(
                    "Çok parçalı indirme tamamlanamadı; tek akışla kaldığı yerden devam ediliyor.",
                    code="SEGMENTED_FALLBACK",
                    suggestion="İndirme iptal edilmedi; daha uyumlu yöntem otomatik seçildi.",
                    lesson_key=lesson.key,
                )
                self.sink.exception("DOWNLOAD", error, lesson_key=lesson.key)

        existing = part.stat().st_size if part.exists() else 0
        headers = dict(base_headers)
        if existing:
            headers["Range"] = f"bytes={existing}-"
        started = time.monotonic()
        last_emit = 0.0
        with session.get(source_url, headers=headers, stream=True, allow_redirects=True, timeout=(20, 90)) as response:
            if response.status_code == 416 and part.exists():
                if total and part.stat().st_size >= total:
                    part.replace(target)
                    return
                part.unlink(missing_ok=True)
                return self.download_direct(source_url, target, cookies, user_agent, referer, lesson)
            response.raise_for_status()
            content_type = (response.headers.get("content-type") or "").lower()
            if "text/html" in content_type:
                raise RuntimeError("Download bağlantısı video yerine giriş/HTML sayfası döndürdü.")
            resumed = existing > 0 and response.status_code == 206
            if existing and not resumed:
                existing = 0
            total_header = response.headers.get("content-length")
            if not total and total_header and total_header.isdigit():
                total = int(total_header) + existing
            mode = "ab" if resumed else "wb"
            written = existing
            with part.open(mode) as handle:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    self.check_control()
                    if not chunk:
                        continue
                    handle.write(chunk)
                    written += len(chunk)
                    now = time.monotonic()
                    if now - last_emit >= 0.2:
                        elapsed = max(now - started, 0.01)
                        speed = max(0.0, (written - existing) / elapsed)
                        eta = max(0.0, (total - written) / speed) if total and speed else 0.0
                        self._emit_download_progress(lesson, written, total, speed, eta, segments=1)
                        last_emit = now
            self._emit_download_progress(lesson, written, total or written, 0.0, 0.0, segments=1)
            part.replace(target)

    def _emit_download_progress(
        self,
        lesson: Lesson,
        written: int,
        total: int,
        speed: float,
        eta: float,
        *,
        segments: int,
    ) -> None:
        progress = min(written / total, 0.995) if total else 0.0
        if total:
            lesson.known_size = total
        lesson.progress = progress
        lesson.bytes_downloaded = written
        lesson.download_speed = speed
        lesson.eta_seconds = eta
        self.sink.emit(
            "item_progress",
            {
                "key": lesson.key,
                "progress": progress,
                "bytes_done": written,
                "bytes_total": total,
                "speed": speed,
                "eta": eta,
                "segments": segments,
                "detail": f"{human_bytes(written)} / {human_bytes(total)} · {human_bytes(int(speed))}/sn" if speed else f"{human_bytes(written)} / {human_bytes(total)}",
            },
        )

    def _download_segmented(
        self,
        source_url: str,
        part: Path,
        cookies: list[dict[str, Any]],
        headers: dict[str, str],
        lesson: Lesson,
        total: int,
        threads: int,
    ) -> None:
        segment_dir = part.parent / "EchoWraith Verileri" / "_gecici" / "segments" / lesson.key
        segment_dir.mkdir(parents=True, exist_ok=True)
        ranges: list[tuple[int, int, Path]] = []
        block = (total + threads - 1) // threads
        for index in range(threads):
            start = index * block
            end = min(total - 1, start + block - 1)
            if start <= end:
                ranges.append((start, end, segment_dir / f"{index:02d}.part"))
        counter_lock = threading.Lock()
        written = sum(min(path.stat().st_size, end - start + 1) for start, end, path in ranges if path.exists())
        initial_written = written
        started = time.monotonic()
        last_emit = 0.0

        def fetch(item: tuple[int, int, Path]) -> None:
            nonlocal written, last_emit
            start, end, path = item
            existing = path.stat().st_size if path.exists() else 0
            expected = end - start + 1
            if existing >= expected:
                return
            own_session = self._requests_session(cookies)
            request_headers = {**headers, "Range": f"bytes={start + existing}-{end}"}
            with own_session.get(source_url, headers=request_headers, stream=True, allow_redirects=True, timeout=(20, 90)) as response:
                if response.status_code != 206:
                    raise RuntimeError(f"Sunucu parça isteğini desteklemedi: HTTP {response.status_code}")
                mode = "ab" if existing else "wb"
                with path.open(mode) as handle:
                    for chunk in response.iter_content(chunk_size=512 * 1024):
                        self.check_control()
                        if not chunk:
                            continue
                        handle.write(chunk)
                        with counter_lock:
                            written += len(chunk)
                            now = time.monotonic()
                            if now - last_emit >= 0.2:
                                speed = max(0.0, (written - initial_written) / max(now - started, 0.01))
                                eta = max(0.0, (total - written) / speed) if speed else 0.0
                                self._emit_download_progress(lesson, written, total, speed, eta, segments=len(ranges))
                                last_emit = now
            if path.stat().st_size != expected:
                raise RuntimeError("İndirilen video parçasının boyutu beklenenden farklı.")

        self.sink.log(
            f"{len(ranges)} parçalı paralel indirme başladı.",
            "info",
            stage="DOWNLOAD",
            code="SEGMENTED_START",
            lesson_key=lesson.key,
        )
        with ThreadPoolExecutor(max_workers=len(ranges), thread_name_prefix="echo-part") as pool:
            futures = [pool.submit(fetch, item) for item in ranges]
            for future in as_completed(futures):
                future.result()
        with part.open("wb") as output:
            for _start, _end, path in ranges:
                with path.open("rb") as source:
                    shutil.copyfileobj(source, output, length=1024 * 1024)
        if part.stat().st_size != total:
            raise RuntimeError("Birleştirilen dosyanın boyutu sunucudaki videoyla eşleşmiyor.")
        shutil.rmtree(segment_dir, ignore_errors=True)
        self._emit_download_progress(lesson, total, total, 0.0, 0.0, segments=len(ranges))

    def download_hls(
        self,
        source_url: str,
        target: Path,
        cookies: list[dict[str, Any]],
        user_agent: str,
        referer: str,
        lesson: Lesson,
    ) -> None:
        self.ensure_tools()
        assert self.ffmpeg
        cookie_line = self._cookie_header(cookies, source_url)
        headers = f"User-Agent: {user_agent}\r\nReferer: {referer or BASE_URL}\r\nCookie: {cookie_line}\r\n"
        part = target.with_suffix(".part.mp4")
        command = [
            self.ffmpeg,
            "-y",
            "-hide_banner",
            "-nostats",
            "-progress",
            "pipe:1",
            "-reconnect",
            "1",
            "-reconnect_streamed",
            "1",
            "-reconnect_delay_max",
            "5",
            "-rw_timeout",
            "30000000",
            "-headers",
            headers,
            "-i",
            source_url,
            "-c",
            "copy",
            "-movflags",
            "+faststart",
            str(part),
        ]
        try:
            self._run_process(command, lesson)
        except RuntimeError as error:
            lesson.recovery_count += 1
            self.sink.recovery(
                "Kayıpsız yayın birleştirme olmadı; uyumlu video dönüştürme deneniyor.",
                code="STREAM_TRANSCODE_FALLBACK",
                suggestion="Bu yöntem daha uzun sürebilir ancak bozuk ses/video akışlarını onarır.",
                lesson_key=lesson.key,
            )
            part.unlink(missing_ok=True)
            fallback = [
                self.ffmpeg,
                "-y",
                "-hide_banner",
                "-nostats",
                "-progress",
                "pipe:1",
                "-reconnect",
                "1",
                "-reconnect_streamed",
                "1",
                "-reconnect_delay_max",
                "5",
                "-headers",
                headers,
                "-i",
                source_url,
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-crf",
                "23",
                "-c:a",
                "aac",
                "-b:a",
                "160k",
                "-movflags",
                "+faststart",
                str(part),
            ]
            self.sink.exception("STREAM", error, lesson_key=lesson.key)
            self._run_process(fallback, lesson)
        part.replace(target)

    def download_external(
        self,
        source_url: str,
        target: Path,
        cookies: list[dict[str, Any]],
        user_agent: str,
        referer: str,
        lesson: Lesson,
    ) -> None:
        cookie_path = CACHE_DIR / "external" / lesson.key / "cookies.txt"
        self.write_netscape_cookies(cookie_path, cookies)
        command = [
            sys.executable,
            "-m",
            "yt_dlp",
            "--no-playlist",
            "--newline",
            "--continue",
            "--concurrent-fragments",
            str(max(1, min(int(self.settings.segment_threads), 8))),
            "--merge-output-format",
            "mp4",
            "--cookies",
            str(cookie_path),
            "--user-agent",
            user_agent,
            "--referer",
            referer or BASE_URL,
            "-f",
            "bv*+ba/b",
            "-o",
            str(target),
            source_url,
        ]
        try:
            self._run_process(command, lesson)
        finally:
            try:
                cookie_path.unlink(missing_ok=True)
            except OSError:
                pass

    def _probe_encoder(self, encoder: str) -> bool:
        """Encode a tiny throwaway clip to learn whether a hardware encoder is
        actually usable on this machine (correct driver, GPU present, etc.)."""
        self.ensure_tools()
        assert self.ffmpeg
        command = [
            self.ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            "testsrc=size=128x72:rate=1:duration=1",
            "-frames:v",
            "1",
            "-c:v",
            encoder,
            "-f",
            "null",
            "-",
        ]
        creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                timeout=45,
                creationflags=creationflags,
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, OSError):
            return False

    def _encoder_available(self, encoder: str) -> bool:
        if encoder == "libx264":
            return True
        available = self._encoder_cache.get(encoder)
        if available is None:
            available = self._probe_encoder(encoder)
            self._encoder_cache[encoder] = available
        return available

    def _best_encoder(self, lesson: Lesson) -> str:
        """Pick the fastest encoder this machine can actually use. Hardware
        encoders finish a merge several times faster than libx264, which matters
        for bulk jobs, and every candidate is probed so the choice never breaks
        the render."""
        for candidate in ("h264_nvenc", "h264_qsv", "h264_amf"):
            if self._encoder_available(candidate):
                self.sink.log(
                    f"Bu bilgisayar için en hızlı uyumlu kodlayıcı seçildi: {candidate}.",
                    "success",
                    stage="ENCODER",
                    code="ENCODER_AUTO",
                    lesson_key=lesson.key,
                )
                return candidate
        return "libx264"

    def _usable_encoder(self, encoder: str, lesson: Lesson) -> str:
        """Fall back to libx264 up front when the requested hardware encoder is
        not available, instead of discovering it only after a full, slow render
        fails partway through."""
        if encoder == "libx264":
            return encoder
        available = self._encoder_cache.get(encoder)
        if available is None:
            available = self._probe_encoder(encoder)
            self._encoder_cache[encoder] = available
        if available:
            return encoder
        lesson.recovery_count += 1
        self.sink.recovery(
            "Seçili donanım kodlayıcı bu bilgisayarda kullanılamıyor; uyumlu işlemci kodlayıcısına (libx264) geçildi.",
            code="ENCODER_UNAVAILABLE",
            suggestion="İşlem libx264 ile sürdürülecek; ayrıca Ayarlar’dan kodlayıcıyı değiştirebilirsiniz.",
            lesson_key=lesson.key,
            active=False,
        )
        return "libx264"

    def download_bbb(self, source: SourceInfo, target: Path, lesson: Lesson, cookies: list[dict[str, Any]]) -> None:
        self.ensure_tools()
        assert self.ffmpeg and self.ffprobe
        work_dir = Path(self.settings.output_dir).expanduser() / "EchoWraith Verileri" / "_gecici" / "bbb" / lesson.key
        work_dir.mkdir(parents=True, exist_ok=True)
        self.write_netscape_cookies(work_dir / "cookies.txt", cookies)

        ffmpeg_dir = Path(self.ffmpeg).parent
        if Path(self.ffprobe).parent != ffmpeg_dir:
            tools_dir = CACHE_DIR / "ffmpeg-tools"
            tools_dir.mkdir(parents=True, exist_ok=True)
            ffmpeg_name = "ffmpeg.exe" if os.name == "nt" else "ffmpeg"
            ffprobe_name = "ffprobe.exe" if os.name == "nt" else "ffprobe"
            shutil.copy2(self.ffmpeg, tools_dir / ffmpeg_name)
            shutil.copy2(self.ffprobe, tools_dir / ffprobe_name)
            ffmpeg_dir = tools_dir

        encoder_map = {
            "libx264 (uyumlu)": "libx264",
            "NVIDIA NVENC": "h264_nvenc",
            "Intel Quick Sync": "h264_qsv",
            "AMD AMF": "h264_amf",
        }
        if self.settings.encoder == "Otomatik (en hızlı)":
            encoder = self._best_encoder(lesson)
        else:
            encoder = self._usable_encoder(encoder_map.get(self.settings.encoder, "libx264"), lesson)
        # The frame-capture phase spins up one headless Chrome per worker and is
        # the slowest part of a BBB render, so scale it to the machine instead of
        # pinning two workers. Capped so a many-core host does not exhaust RAM.
        parallel_chromes = max(2, min(os.cpu_count() or 2, 4))
        command = locate_bbb_cli() + [
            source.source_url,
            "--ffmpeg-location",
            str(ffmpeg_dir),
            "--working-dir",
            str(work_dir),
            "--output-dir",
            str(target.parent),
            "--filename",
            target.name,
            "--encoder",
            encoder,
            "--preset",
            "veryfast" if encoder == "libx264" else "fast",
            "--crf",
            "23",
            "--max-parallel-chromes",
            str(parallel_chromes),
            "--keep-tmp-files",
            "--skip-webcam",
        ]
        if self.settings.quality == "Hızlı (720p)":
            command += ["--force-width", "1280", "--force-height", "720", "--skip-cursor"]
        elif self.settings.quality == "Yüksek (1080p)":
            command += ["--force-width", "1920", "--force-height", "1080"]
        else:
            command += ["--force-width", "1280", "--force-height", "720"]

        process_env = {
            "ECHOWRAITH_BBB_REFERER": source.referer or BASE_URL,
            "ECHOWRAITH_BBB_USER_AGENT": self.site.user_agent(),
        }

        try:
            self._run_process(
                command,
                lesson,
                extra_env=process_env,
                stall_timeout=900.0,
            )
        except RuntimeError as first_error:
            last_error = first_error
            if encoder != "libx264":
                lesson.recovery_count += 1
                self.sink.recovery(
                    "Donanım kodlayıcı uyum sağlamadı; işlemciyle uyumlu kodlayıcı deneniyor. Lütfen bekleyin.",
                    code="ENCODER_FALLBACK",
                    suggestion="Kayıt libx264 ile yeniden oluşturulacak.",
                    lesson_key=lesson.key,
                )
                target.unlink(missing_ok=True)
                encoder_index = command.index("--encoder") + 1
                preset_index = command.index("--preset") + 1
                command[encoder_index] = "libx264"
                command[preset_index] = "veryfast"
                try:
                    self._run_process(command, lesson, extra_env=process_env, stall_timeout=900.0)
                    last_error = None
                except RuntimeError as software_error:
                    last_error = software_error

            # bbb-dl documents this narrowly-scoped option. It is only used
            # after an actual certificate validation failure and never as a
            # default, preserving normal HTTPS verification for every run.
            error_text = str(last_error or "").casefold()
            certificate_error = any(
                marker in error_text
                for marker in (
                    "certificate verify failed",
                    "certificate validation",
                    "unable to get local issuer",
                    "self signed certificate",
                    "ssl: cert",
                )
            )
            if last_error is not None and certificate_error:
                lesson.recovery_count += 1
                self.sink.recovery(
                    "Kayıt sunucusunun sertifika zinciri doğrulanamadı; yalnız bu kayıt için uyumluluk modu deneniyor.",
                    code="BBB_CERT_COMPAT",
                    suggestion="Bu seçenek yalnız sertifika hatası görüldüğünde ve yalnız ilgili BBB isteğinde kullanılır.",
                    lesson_key=lesson.key,
                )
                target.unlink(missing_ok=True)
                if "--skip-cert-verify" not in command:
                    command.append("--skip-cert-verify")
                try:
                    self._run_process(command, lesson, extra_env=process_env, stall_timeout=900.0)
                    last_error = None
                except RuntimeError as certificate_retry_error:
                    last_error = certificate_retry_error

            error_text = str(last_error or "").casefold()
            protocol_error = any(
                marker in error_text
                for marker in (
                    "protocol version",
                    "wrong version number",
                    "tlsv1 alert protocol",
                    "legacy renegotiation",
                    "unsafe legacy",
                )
            )
            if last_error is not None and protocol_error:
                lesson.recovery_count += 1
                self.sink.recovery(
                    "Kayıt sunucusu eski bir TLS sürümü kullanıyor; yalnız bu kayıt için protokol uyumluluğu deneniyor.",
                    code="BBB_TLS_COMPAT",
                    suggestion="Diğer tüm bağlantılarda normal güvenli TLS ayarları korunur.",
                    lesson_key=lesson.key,
                )
                target.unlink(missing_ok=True)
                if "--allow-insecure-ssl" not in command:
                    command.append("--allow-insecure-ssl")
                try:
                    self._run_process(command, lesson, extra_env=process_env, stall_timeout=900.0)
                    last_error = None
                except RuntimeError as protocol_retry_error:
                    last_error = protocol_retry_error

            error_text = str(last_error or "").casefold()
            cipher_error = any(marker in error_text for marker in ("no shared cipher", "cipher mismatch", "handshake failure"))
            if last_error is not None and cipher_error:
                lesson.recovery_count += 1
                self.sink.recovery(
                    "Kayıt sunucusunun şifreleme takımı eski; son uyumluluk yöntemi yalnız bu kayıt için deneniyor.",
                    code="BBB_CIPHER_COMPAT",
                    suggestion="İşlem bitince uyumluluk ayarı kapanır.",
                    lesson_key=lesson.key,
                )
                target.unlink(missing_ok=True)
                if "--use-all-ciphers" not in command:
                    command.append("--use-all-ciphers")
                self._run_process(command, lesson, extra_env=process_env, stall_timeout=900.0)
                last_error = None

            if last_error is not None:
                raise last_error
        if not target.exists():
            matches = sorted(target.parent.glob(f"{target.stem}*.mp4"), key=lambda item: item.stat().st_mtime, reverse=True)
            if matches:
                matches[0].replace(target)
        if not target.exists() or target.stat().st_size < 1024:
            raise RuntimeError("BBB dönüştürme tamamlandı görünse de MP4 dosyası oluşmadı.")
        assets_dir = Path(self.settings.output_dir).expanduser() / "EchoWraith Verileri" / lesson.key
        assets_dir.mkdir(parents=True, exist_ok=True)
        webcam = self.archive_webcam(work_dir, assets_dir)
        if webcam:
            lesson.webcam_path = str(webcam)
        if self.settings.save_chat:
            chat_txt, chat_json = self.export_bbb_chat(work_dir, assets_dir)
            if chat_txt:
                lesson.chat_path = str(chat_txt)
            if chat_json:
                lesson.chat_json_path = str(chat_json)
        shutil.rmtree(work_dir, ignore_errors=True)
        self.sink.log(
            "BBB geçici çalışma dosyaları güvenli biçimde temizlendi.",
            "success",
            stage="CLEANUP",
            code="BBB_CACHE_CLEAN",
            lesson_key=lesson.key,
        )

    def convert_webm_to_mp4(self, source: Path, target: Path, lesson: Lesson) -> None:
        self.ensure_tools()
        assert self.ffmpeg
        part = target.with_suffix(".donusturuluyor.mp4")
        command = [
            self.ffmpeg,
            "-y",
            "-hide_banner",
            "-i",
            str(source),
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "23",
            "-c:a",
            "aac",
            "-b:a",
            "160k",
            "-movflags",
            "+faststart",
            str(part),
        ]
        self._run_process(command, lesson)
        part.replace(target)
        try:
            source.unlink()
        except OSError:
            pass

    def _terminate_process(self, process: Optional[subprocess.Popen[str]] = None) -> None:
        with self._process_lock:
            process = process or self.current_process
        if process is None or process.poll() is not None:
            return
        # FFmpeg/BBB-dl may spawn Chromium and more FFmpeg children. Killing
        # only the direct parent leaves those processes running on Windows and
        # is the reason an old Stop could continue consuming CPU/RAM. Every
        # child is launched in its own process group and the whole tree is
        # terminated here.
        try:
            if os.name == "nt":
                subprocess.run(
                    ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=12,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                    check=False,
                )
            else:
                os.killpg(process.pid, signal.SIGTERM)
            process.wait(timeout=5)
        except (subprocess.TimeoutExpired, ProcessLookupError):
            try:
                if os.name != "nt":
                    os.killpg(process.pid, signal.SIGKILL)
                else:
                    process.kill()
                process.wait(timeout=5)
            except Exception:
                pass
        except Exception:
            try:
                process.kill()
            except Exception:
                pass

    def cancel(self) -> None:
        """Stop network loops and the active external process immediately."""
        self.stop_event.set()
        self.pause_event.set()
        self._terminate_process()

    def _run_process(
        self,
        command: list[str],
        lesson: Lesson,
        extra_env: Optional[dict[str, str]] = None,
        *,
        stall_timeout: float = 600.0,
    ) -> None:
        creationflags = 0
        popen_kwargs: dict[str, Any] = {}
        if os.name == "nt":
            creationflags = subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            popen_kwargs["start_new_session"] = True
        env = os.environ.copy()
        env["PYTHONUTF8"] = "1"
        if extra_env:
            env.update(extra_env)
        with self._process_lock:
            self.current_process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                creationflags=creationflags,
                env=env,
                **popen_kwargs,
            )
            process = self.current_process
        started = time.monotonic()
        last_emit = 0.0
        last_progress = -1.0
        tail: deque[str] = deque(maxlen=12)

        # ffmpeg/bbb-dl emit progress on a carriage return without a trailing
        # newline, so iterating the pipe can block indefinitely with no way to
        # notice a wedged child or an in-flight Stop. A daemon reader thread
        # feeds a queue we poll with a timeout; that lets us honour Stop within
        # a second and treat a long silence as a stall instead of hanging here
        # for the rest of the session.
        line_queue: "queue.Queue[Optional[str]]" = queue.Queue(maxsize=8192)

        def _pump() -> None:
            try:
                assert process.stdout
                for raw in process.stdout:
                    line_queue.put(raw)
            except Exception:
                pass
            finally:
                line_queue.put(None)

        reader = threading.Thread(target=_pump, name="echo-proc-reader", daemon=True)
        reader.start()
        last_activity = time.monotonic()
        try:
            while True:
                try:
                    raw = line_queue.get(timeout=1.0)
                except queue.Empty:
                    if self.stop_event.is_set():
                        self._terminate_process(process)
                        raise CancelledError("Dönüştürme durduruldu.")
                    if stall_timeout and (time.monotonic() - last_activity) > stall_timeout:
                        self._terminate_process(process)
                        summary = " | ".join(tail)[-1200:]
                        raise RuntimeError(
                            f"Dönüştürücü {int(stall_timeout)} saniye boyunca ilerleme bildirmedi ve durduruldu. {summary}"
                        )
                    continue
                if raw is None:
                    break
                last_activity = time.monotonic()
                if self.stop_event.is_set():
                    self._terminate_process(process)
                    raise CancelledError("Dönüştürme durduruldu.")
                line = strip_ansi(raw).strip()
                if not line:
                    continue
                tail.append(line)
                self.sink.log(line, "debug", stage="PROCESS", lesson_key=lesson.key)
                percent = re.search(r"(?<!\d)(\d{1,3}(?:\.\d+)?)\s*%", line)
                value = min(float(percent.group(1)) / 100, 0.995) if percent else -1.0
                clock = re.search(r"(?:out_time|time)=(\d{1,2}):(\d{2}):(\d{2}(?:\.\d+)?)", line)
                micros = re.search(r"out_time_(?:ms|us)=(\d+)", line)
                position = 0.0
                if clock:
                    position = int(clock.group(1)) * 3600 + int(clock.group(2)) * 60 + float(clock.group(3))
                elif micros:
                    position = int(micros.group(1)) / 1_000_000
                if position and lesson.duration:
                    value = max(value, min(position / lesson.duration, 0.995))
                # bbb-dl reports its own progress without a percent sign, so the
                # bar used to sit at 0 for the whole (long) render. Map its two
                # main phases onto a single forward-moving bar: frame capture is
                # the first ~60%, the slideshow/mux the rest.
                frame_capture = re.search(r"Done:\s*(\d+)\s*/\s*(\d+)\s*Frames", line, re.I)
                if frame_capture and int(frame_capture.group(2)) > 0:
                    captured = int(frame_capture.group(1)) / int(frame_capture.group(2))
                    value = max(value, min(0.04 + captured * 0.56, 0.6))
                if "creating slideshow" in line.casefold():
                    value = max(value, 0.6)
                bbb_time = re.search(r"\bTime:\s*(\d+(?::\d{2}){0,2})\b", line)
                if bbb_time and lesson.duration:
                    parts = [int(part) for part in bbb_time.group(1).split(":")]
                    seconds = 0
                    for part in parts:
                        seconds = seconds * 60 + part
                    value = max(value, min(0.6 + (seconds / lesson.duration) * 0.36, 0.97))
                speed = 0.0
                speed_match = re.search(r"([\d.]+)\s*(KiB|MiB|GiB|KB|MB|GB)/s", line, re.I)
                if speed_match:
                    multiplier = {"kib": 1024, "mib": 1024**2, "gib": 1024**3, "kb": 1000, "mb": 1000**2, "gb": 1000**3}[speed_match.group(2).casefold()]
                    speed = float(speed_match.group(1)) * multiplier
                process_speed = re.search(r"\bspeed\s*=\s*([\d.]+)x", line, re.I)
                eta_match = re.search(r"\bETA\s+(?:(\d+):)?(\d{1,2}):(\d{2})\b", line, re.I)
                now = time.monotonic()
                if value >= 0 and (now - last_emit >= 0.2 or value >= 0.995) and abs(value - last_progress) >= 0.001:
                    if eta_match:
                        eta = int(eta_match.group(1) or 0) * 3600 + int(eta_match.group(2)) * 60 + int(eta_match.group(3))
                    elif position and lesson.duration:
                        eta = max(0.0, lesson.duration - position)
                        if process_speed and float(process_speed.group(1)) > 0:
                            eta /= float(process_speed.group(1))
                    else:
                        eta = 0.0
                    lesson.progress = value
                    lesson.download_speed = speed
                    lesson.eta_seconds = eta
                    self.sink.emit(
                        "item_progress",
                        {
                            "key": lesson.key,
                            "progress": value,
                            "speed": speed,
                            "eta": eta,
                            "elapsed": now - started,
                            "detail": line[-110:],
                        },
                    )
                    last_emit = now
                    last_progress = value
            code = process.wait()
            reader.join(timeout=5)
            if self.stop_event.is_set():
                raise CancelledError("Dönüştürme kullanıcı tarafından durduruldu.")
            if code != 0:
                summary = " | ".join(tail)[-1200:]
                raise RuntimeError(f"Dönüştürücü hata koduyla kapandı: {code}. {summary}")
        finally:
            self._terminate_process(process)
            self.current_process = None

    @staticmethod
    def archive_webcam(work_dir: Path, assets_dir: Path) -> Optional[Path]:
        candidates = [
            path
            for pattern in ("webcams.webm", "webcams.mp4")
            for path in work_dir.rglob(pattern)
            if path.is_file() and path.stat().st_size > 1024
        ]
        if not candidates:
            return None
        source = max(candidates, key=lambda path: path.stat().st_size)
        target = assets_dir / f"webcam{source.suffix.lower()}"
        if not target.exists() or target.stat().st_size != source.stat().st_size:
            shutil.copy2(source, target)
        return target

    @staticmethod
    def _normalize_chat_time(raw_value: Any, start_ms: float, duration: float) -> float:
        try:
            value = float(str(raw_value or "0").replace(",", "."))
        except ValueError:
            return 0.0
        if value > 1_000_000_000_000:
            value = (value - start_ms) / 1000.0 if start_ms else value / 1000.0
        elif value > 1_000_000_000:
            value = value - (start_ms / 1000.0 if start_ms else value)
        elif duration and value > duration * 20:
            value /= 1000.0
        return max(0.0, value)

    @classmethod
    def export_bbb_chat(cls, work_dir: Path, assets_dir: Path) -> tuple[Optional[Path], Optional[Path]]:
        candidates = list(work_dir.rglob("events.xml"))
        if not candidates:
            return None, None
        start_ms = 0.0
        duration = 0.0
        metadata_candidates = list(work_dir.rglob("metadata.xml"))
        if metadata_candidates:
            try:
                metadata_root = ET.parse(metadata_candidates[0]).getroot()
                start_ms = float(metadata_root.findtext("start_time") or 0)
                duration = float(metadata_root.findtext("./playback/duration") or 0) / 1000.0
            except (OSError, ET.ParseError, ValueError):
                pass
        messages: list[dict[str, Any]] = []
        try:
            root = ET.parse(candidates[0]).getroot()
            for event in root.iter("event"):
                event_name = (event.attrib.get("eventname") or "").lower()
                if "chat" not in event_name:
                    continue
                sender = event.findtext("sender") or event.findtext("name") or "Katılımcı"
                message = event.findtext("message") or event.findtext("body") or ""
                timestamp = event.attrib.get("timestamp") or event.findtext("timestamp") or ""
                message = re.sub(r"<[^>]+>", "", html.unescape(message)).strip()
                if message:
                    sender = re.sub(r"\s+", " ", html.unescape(sender)).strip()
                    role = (event.attrib.get("role") or event.findtext("role") or "").lower()
                    messages.append(
                        {
                            "time": round(cls._normalize_chat_time(timestamp, start_ms, duration), 3),
                            "sender": sender or "Katılımcı",
                            "text": message,
                            "teacher": any(token in f"{sender.lower()} {role}" for token in ("öğretmen", "teacher", "moderator", "hoca")),
                        }
                    )
        except (OSError, ET.ParseError):
            return None, None
        if not messages:
            return None, None
        messages.sort(key=lambda item: item["time"])
        assets_dir.mkdir(parents=True, exist_ok=True)
        txt_target = assets_dir / "sohbet.txt"
        json_target = assets_dir / "sohbet.json"
        txt_target.write_text(
            "\n".join(f"[{format_seconds(item['time'])}] {item['sender']}: {item['text']}" for item in messages) + "\n",
            encoding="utf-8",
        )
        json_target.write_text(json.dumps(messages, ensure_ascii=False, indent=2), encoding="utf-8")
        return txt_target, json_target

    @staticmethod
    def save_chat(text: str, target: Path) -> str:
        cleaned = re.sub(r"\n{3,}", "\n\n", text or "").strip()
        if not cleaned:
            return ""
        target.write_text(cleaned + "\n", encoding="utf-8")
        return str(target)

    @classmethod
    def save_chat_bundle(cls, text: str, assets_dir: Path) -> tuple[str, str]:
        cleaned = re.sub(r"\n{3,}", "\n\n", text or "").strip()
        if not cleaned:
            return "", ""
        assets_dir.mkdir(parents=True, exist_ok=True)
        txt_target = assets_dir / "sohbet.txt"
        json_target = assets_dir / "sohbet.json"
        txt_target.write_text(cleaned + "\n", encoding="utf-8")
        lines = [line.strip() for line in cleaned.splitlines() if line.strip()]
        messages: list[dict[str, Any]] = []
        pending_sender = "Katılımcı"
        pending_time = 0.0
        for line in lines:
            time_match = re.search(r"\b(?:(\d{1,2}):)?(\d{1,2}):(\d{2})\b", line)
            if time_match:
                hours = int(time_match.group(1) or 0)
                pending_time = hours * 3600 + int(time_match.group(2)) * 60 + int(time_match.group(3))
                sender_part = line[: time_match.start()].strip(" -–—:")
                if sender_part:
                    pending_sender = sender_part[-80:]
                remainder = line[time_match.end() :].strip(" -–—:")
                if remainder:
                    messages.append(
                        {
                            "time": pending_time,
                            "sender": pending_sender,
                            "text": remainder,
                            "teacher": any(token in pending_sender.lower() for token in ("öğretmen", "hoca", "teacher")),
                        }
                    )
                continue
            if len(line) > 1:
                messages.append(
                    {
                        "time": pending_time,
                        "sender": pending_sender,
                        "text": line,
                        "teacher": any(token in pending_sender.lower() for token in ("öğretmen", "hoca", "teacher")),
                    }
                )
        json_target.write_text(json.dumps(messages, ensure_ascii=False, indent=2), encoding="utf-8")
        return str(txt_target), str(json_target)

    def verify_output(self, target: Path) -> float:
        if not target.exists() or target.stat().st_size < 1024:
            raise RuntimeError("İndirilen dosya boş veya eksik.")
        self.ensure_tools()
        assert self.ffprobe
        result = subprocess.run(
            [self.ffprobe, "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(target)],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0:
            raise RuntimeError("Dosya indi fakat video doğrulaması başarısız oldu.")
        try:
            duration = float(result.stdout.strip())
            if duration <= 0.1:
                raise RuntimeError("Video süresi geçersiz görünüyor.")
            return duration
        except ValueError as exc:
            raise RuntimeError("Video süresi okunamadı.") from exc

    def assets_for(self, lesson: Lesson) -> Path:
        return Path(self.settings.output_dir).expanduser() / "EchoWraith Verileri" / lesson.key

    def repair_output(self, target: Path, lesson: Lesson) -> None:
        self.ensure_tools()
        assert self.ffmpeg
        repaired = target.with_suffix(".onariliyor.mp4")
        repaired.unlink(missing_ok=True)
        command = [
            self.ffmpeg,
            "-y",
            "-hide_banner",
            "-err_detect",
            "ignore_err",
            "-i",
            str(target),
            "-map",
            "0:v:0?",
            "-map",
            "0:a:0?",
            "-c",
            "copy",
            "-movflags",
            "+faststart",
            str(repaired),
        ]
        self._run_process(command, lesson)
        if not repaired.is_file() or repaired.stat().st_size < 1024:
            raise RuntimeError("Otomatik video onarımı dosya üretemedi.")
        repaired.replace(target)

    def generate_thumbnail(self, target: Path, lesson: Lesson) -> Optional[Path]:
        if not self.settings.auto_thumbnail:
            return None
        self.ensure_tools()
        assert self.ffmpeg
        assets = self.assets_for(lesson)
        assets.mkdir(parents=True, exist_ok=True)
        thumbnail = assets / "onizleme.jpg"
        seek = min(max(5.0, lesson.duration * 0.12), max(5.0, lesson.duration - 2.0))
        command = [
            self.ffmpeg,
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-ss",
            str(seek),
            "-i",
            str(target),
            "-frames:v",
            "1",
            "-vf",
            "scale=720:-2",
            "-q:v",
            "4",
            str(thumbnail),
        ]
        result = subprocess.run(command, capture_output=True, text=True, timeout=90)
        if result.returncode == 0 and thumbnail.is_file() and thumbnail.stat().st_size > 1024:
            lesson.thumbnail_path = str(thumbnail)
            self.sink.log("Video önizleme görseli hazırlandı.", "success", stage="THUMBNAIL", lesson_key=lesson.key)
            return thumbnail
        self.sink.log(
            "Video önizleme karesi üretilemedi; tematik arka plan kullanılacak.",
            "warning",
            stage="THUMBNAIL",
            code="THUMBNAIL_FALLBACK",
            details=result.stderr[-500:],
            lesson_key=lesson.key,
        )
        return None

    def process(self, lesson: Lesson) -> Lesson:
        target = self.target_for(lesson)
        lesson.attempts += 1
        lesson.status = "Kaynak aranıyor"
        lesson.error = ""
        self.sink.emit("lesson_update", asdict(lesson))
        self.sink.stage("SOURCE", f"{lesson.title}: kayıt türü analiz ediliyor…", progress=0.04, lesson_key=lesson.key)
        view = self.site.open_lesson(lesson)
        try:
            source: SourceInfo | None = None
            last_error: Exception | None = None
            for attempt in range(1, 4):
                try:
                    source = self.site.inspect_source(view)
                    break
                except Exception as error:
                    last_error = error
                    lesson.recovery_count += 1
                    diagnosis = diagnose_exception(error)
                    self.sink.recovery(
                        f"Kayıt kaynağı ilk yöntemde bulunamadı; alternatif tarama {attempt}/3 deneniyor.",
                        code=diagnosis["code"],
                        suggestion=diagnosis["suggestion"],
                        lesson_key=lesson.key,
                    )
                    if attempt < 3:
                        try:
                            view.page.reload(wait_until="domcontentloaded")
                        except Exception:
                            pass
                        view.page.wait_for_timeout(900 * attempt)
            if source is None and self.site.headless_active:
                self.site.close_lesson(view)
                self.site.restart_visible()
                self.site.ensure_login()
                view = self.site.open_lesson(lesson)
                source = self.site.inspect_source(view)
            if source is None:
                raise last_error or RuntimeError("Ders kaynağı bulunamadı.")
            lesson.source_type = source.source_type
            # Signed recording URLs and one-time access parameters are needed
            # only in memory while this method runs; never persist them.
            lesson.source_url = ""
            lesson.meeting_id = source.meeting_id
            lesson.known_size = source.size
            lesson.status = "İndiriliyor" if source.source_type != "BBB / TUES" else "Birleştiriliyor"
            self.sink.emit("lesson_update", asdict(lesson))
            self.sink.log(
                f"{lesson.title}: {source.source_type} kaydı bulundu.",
                "success",
                stage="SOURCE",
                code="SOURCE_READY",
                lesson_key=lesson.key,
            )

            cookies = self.site.cookies()
            user_agent = self.site.user_agent()
            if self.settings.save_chat and source.chat_text:
                assets_dir = self.assets_for(lesson)
                lesson.chat_path, lesson.chat_json_path = self.save_chat_bundle(source.chat_text, assets_dir)

            if source.source_type == "BBB / TUES":
                self.download_bbb(source, target, lesson, cookies)
            elif source.source_type in {"HLS", "DASH"}:
                self.download_hls(source.source_url, target, cookies, user_agent, source.referer, lesson)
            elif source.source_type == "Harici video":
                self.download_external(source.source_url, target, cookies, user_agent, source.referer, lesson)
            else:
                if re.search(r"\.webm(?:[?#]|$)", source.source_url, re.I):
                    raw_target = target.with_suffix(".kaynak.webm")
                    try:
                        self.download_direct(source.source_url, raw_target, cookies, user_agent, source.referer, lesson)
                    except Exception as direct_error:
                        lesson.recovery_count += 1
                        self.sink.recovery(
                            "WebM bağlantısı doğrudan yanıt vermedi; tarayıcının Download düğmesi deneniyor.",
                            code="WEBM_BROWSER_FALLBACK",
                            suggestion="Aynı oturum tarayıcı içinde kullanılarak kaynak dosya alınacak.",
                            lesson_key=lesson.key,
                        )
                        self.sink.exception("DOWNLOAD", direct_error, lesson_key=lesson.key)
                        self.site.click_download_fallback(view.page, raw_target)
                    lesson.status = "Dönüştürülüyor"
                    self.sink.emit("lesson_update", asdict(lesson))
                    self.convert_webm_to_mp4(raw_target, target, lesson)
                else:
                    try:
                        self.download_direct(source.source_url, target, cookies, user_agent, source.referer, lesson)
                    except Exception as direct_error:
                        lesson.recovery_count += 1
                        self.sink.recovery(
                            "Doğrudan indirme olmadı; tarayıcının kendi Download bağlantısı deneniyor.",
                            code="BROWSER_DOWNLOAD_FALLBACK",
                            suggestion="Oturum bilgileri tarayıcı içinde kullanılarak kayıt alınacak.",
                            lesson_key=lesson.key,
                        )
                        self.sink.exception("DOWNLOAD", direct_error, lesson_key=lesson.key)
                        self.site.click_download_fallback(view.page, target)

            self.sink.stage("VERIFY", "İndirilen video doğrulanıyor…", progress=0.97, lesson_key=lesson.key)
            try:
                lesson.duration = self.verify_output(target)
            except Exception as verify_error:
                lesson.recovery_count += 1
                self.sink.recovery(
                    "Video doğrulaması başarısız oldu; dosya otomatik onarılıyor. Lütfen bekleyin.",
                    code="MEDIA_REPAIR",
                    suggestion="Ses ve görüntü akışları yeniden paketlenecek.",
                    lesson_key=lesson.key,
                )
                self.sink.exception("VERIFY", verify_error, lesson_key=lesson.key)
                try:
                    self.repair_output(target, lesson)
                    lesson.duration = self.verify_output(target)
                except Exception as repair_error:
                    self.sink.exception("REPAIR", repair_error, lesson_key=lesson.key)
                    failed_dir = CACHE_DIR / "failed-media"
                    failed_dir.mkdir(parents=True, exist_ok=True)
                    if target.exists():
                        quarantine = failed_dir / f"{lesson.key}-{int(time.time())}{target.suffix}"
                        try:
                            target.replace(quarantine)
                        except OSError:
                            target.unlink(missing_ok=True)
                    raise RuntimeError("Video otomatik onarılamadı; bozuk çıktı ayrıldı ve kayıt yeniden indirilecek.") from repair_error
            lesson.output_path = str(target)
            self.generate_thumbnail(target, lesson)
            lesson.status = "Tamamlandı"
            lesson.progress = 1.0
            lesson.bytes_downloaded = target.stat().st_size
            lesson.known_size = target.stat().st_size
            lesson.download_speed = 0.0
            lesson.eta_seconds = 0.0
            lesson.error = ""
            self.sink.recovery("Otomatik işlemler tamamlandı.", code="RECOVERY_DONE", suggestion="", lesson_key=lesson.key, active=False)
            self.sink.log(f"Tamamlandı: {target.name}", "success", stage="COMPLETE", code="LESSON_READY", lesson_key=lesson.key)
            return lesson
        finally:
            self.site.close_lesson(view)


class WorkerController:
    def __init__(self, store: StateStore, events: EventBroker):
        self.store = store
        self.sink = EventSink(events)
        self.stop_event = threading.Event()
        self.pause_event = threading.Event()
        self.pause_event.set()
        self.thread: Optional[threading.Thread] = None
        self.job_label = "Hazır"
        self.job_title = ""
        self.progress_done = 0
        self.progress_total = 0
        self.current_job_type = "idle"
        self.last_finished_at = time.monotonic()
        self.active_engine: Optional[DownloadEngine] = None

    @property
    def busy(self) -> bool:
        return bool(self.thread and self.thread.is_alive())

    @property
    def stopping(self) -> bool:
        return bool(self.busy and self.stop_event.is_set())

    def _interruptible_sleep(self, seconds: float) -> None:
        deadline = time.monotonic() + max(0.0, seconds)
        while time.monotonic() < deadline:
            if self.stop_event.is_set():
                return
            time.sleep(0.1)

    def _start(self, target: Callable[[], None]) -> None:
        if self.busy:
            raise RuntimeError("Başka bir işlem hâlâ çalışıyor.")
        self.stop_event.clear()
        self.pause_event.set()
        def guarded() -> None:
            try:
                target()
            finally:
                self.last_finished_at = time.monotonic()
                self.current_job_type = "idle"
                self._cleanup_cache()

        self.thread = threading.Thread(target=guarded, daemon=True, name="echowraith-worker")
        self.thread.start()

    def _cleanup_cache(self) -> None:
        output_temp = Path(self.store.settings.output_dir).expanduser() / "EchoWraith Verileri" / "_gecici"
        for cookie_file in [*CACHE_DIR.rglob("cookies.txt"), *output_temp.rglob("cookies.txt")]:
            try:
                cookie_file.unlink(missing_ok=True)
            except OSError:
                continue
        cutoff = time.time() - 7 * 24 * 3600
        for pattern in ("browser-downloads/*", "segments/*/*", "external/*/*", "failed-media/*"):
            for path in CACHE_DIR.glob(pattern):
                try:
                    if path.is_file() and path.stat().st_mtime < cutoff:
                        path.unlink()
                except OSError:
                    continue
        if output_temp.is_dir():
            for path in sorted(output_temp.rglob("*"), key=lambda item: len(item.parts), reverse=True):
                try:
                    if path.is_file() and path.stat().st_mtime < cutoff:
                        path.unlink()
                    elif path.is_dir() and not any(path.iterdir()):
                        path.rmdir()
                except OSError:
                    continue
        DIAGNOSTICS.cleanup()

    def authenticate(self, email: str, password: str) -> None:
        if self.busy:
            raise RuntimeError("Başka bir işlem hâlâ çalışıyor.")
        self.current_job_type = "auth"
        self.job_label = "Oturum açılıyor"
        self.job_title = "Efsane Uzem bağlantısı"
        def job() -> None:
            self.sink.emit("job_started", "Oturum açılıyor")
            try:
                with SiteAutomation(self.sink, self.stop_event, self.pause_event, headless_first=self.store.settings.headless_first) as site:
                    site.ensure_login(email, password)
                    self.store.profile = site.extract_profile()
                    self.store.save()
                self.sink.emit("job_done", "Oturum hazır")
            except CancelledError as exc:
                self.sink.emit("job_cancelled", str(exc))
            except Exception as exc:
                self._report_error(exc)

        self._start(job)

    def scan(self, email: str, password: str) -> None:
        if self.busy:
            raise RuntimeError("Başka bir işlem hâlâ çalışıyor.")
        self.current_job_type = "scan"
        self.job_label = "Dersler taranıyor"
        self.job_title = "Video ders listesi"
        def job() -> None:
            self.sink.emit("job_started", "Dersler taranıyor")
            try:
                with SiteAutomation(self.sink, self.stop_event, self.pause_event, headless_first=self.store.settings.headless_first) as site:
                    site.ensure_login(email, password)
                    self.store.profile = site.extract_profile()
                    scanned = site.scan_lessons()
                merged = self.store.merge_scan(scanned)
                self.sink.emit("scan_complete", [asdict(item) for item in merged])
                self.sink.emit("job_done", f"{len(merged)} ders bulundu")
            except CancelledError as exc:
                self.sink.emit("job_cancelled", str(exc))
            except Exception as exc:
                self._report_error(exc)

        self._start(job)

    def download(self, keys: list[str], email: str, password: str) -> None:
        if self.busy:
            raise RuntimeError("Başka bir işlem hâlâ çalışıyor.")
        self.current_job_type = "download"
        self.job_label = "İndirme hazırlanıyor"
        self.job_title = "Kuyruk başlatılıyor"
        self.progress_done = 0
        self.progress_total = len(keys)
        def job() -> None:
            self.sink.emit("job_started", "İndirme hazırlanıyor")
            try:
                output = Path(self.store.settings.output_dir).expanduser()
                output.mkdir(parents=True, exist_ok=True)
                free = shutil.disk_usage(output).free
                if free < 5 * 1024**3:
                    raise RuntimeError(f"Hedef diskte yalnızca {human_bytes(free)} boş alan var; en az 5 GB boşluk bırak.")
                lessons = [self.store.lessons[key] for key in keys if key in self.store.lessons]
                if not lessons:
                    raise RuntimeError("İndirilecek ders seçilmedi.")

                completed = 0
                with SiteAutomation(self.sink, self.stop_event, self.pause_event, headless_first=self.store.settings.headless_first) as site:
                    site.ensure_login(email, password)
                    self.store.profile = site.extract_profile()
                    engine = DownloadEngine(site, self.sink, self.stop_event, self.pause_event, self.store.settings)
                    self.active_engine = engine
                    for index, lesson in enumerate(lessons, start=1):
                        self.progress_done = index - 1
                        self.progress_total = len(lessons)
                        self.job_title = lesson.title
                        site.check_control()
                        target = engine.target_for(lesson)
                        if lesson.status == "Tamamlandı" and target.exists():
                            completed += 1
                            self.sink.emit("overall_progress", {"done": index, "total": len(lessons), "title": lesson.title})
                            continue
                        self.sink.emit("status", f"{index}/{len(lessons)} · {lesson.title}")
                        final_error: Exception | None = None
                        for attempt in range(1, 4):
                            if self.stop_event.is_set():
                                raise CancelledError("Dönüştürme durduruldu.")
                            try:
                                updated = engine.process(lesson)
                                self.store.lessons[updated.key] = updated
                                completed += 1
                                final_error = None
                                break
                            except CancelledError:
                                raise
                            except Exception as exc:
                                final_error = exc
                                diagnosis = self.sink.exception("LESSON", exc, lesson_key=lesson.key, attempt=attempt)
                                if attempt >= 3 or not diagnosis["recoverable"] or self.stop_event.is_set():
                                    break
                                lesson.recovery_count += 1
                                delay = min(10.0, 1.4**attempt + random.random())
                                self.sink.recovery(
                                    f"{lesson.title}: otomatik çözüm {attempt}/2 uygulanıyor. Lütfen bekleyin.",
                                    code=diagnosis["code"],
                                    suggestion=diagnosis["suggestion"],
                                    lesson_key=lesson.key,
                                )
                                self._interruptible_sleep(delay)
                        if self.stop_event.is_set():
                            raise CancelledError("Dönüştürme durduruldu.")
                        if final_error is not None:
                            diagnosis = diagnose_exception(final_error)
                            lesson.status = "Hata"
                            lesson.error = f"{diagnosis['reason']} {diagnosis['suggestion']}"
                            lesson.progress = 0.0
                            lesson.download_speed = 0.0
                            lesson.eta_seconds = 0.0
                            self.store.lessons[lesson.key] = lesson
                            self.sink.emit("lesson_update", asdict(lesson))
                            self.sink.recovery(
                                "Otomatik yöntemler tükendi; ayrıntılı tanılama kaydı hazırlandı.",
                                code=diagnosis["code"],
                                suggestion="Tanılama bölümünden destek paketini indirebilirsiniz.",
                                lesson_key=lesson.key,
                                active=False,
                            )
                        self.progress_done = index
                        self.store.save()
                        self.sink.emit("overall_progress", {"done": index, "total": len(lessons), "title": lesson.title})
                        self._interruptible_sleep(max(0.0, self.store.settings.request_delay))
                self.sink.emit("job_done", f"{completed}/{len(lessons)} ders tamamlandı")
            except CancelledError as exc:
                # A stopped lesson must not keep a transient status, or it would
                # look like it is still merging forever after the user hit Stop.
                for lesson in self.store.lessons.values():
                    if lesson.status in TRANSIENT_STATUSES:
                        lesson.status = "Bekliyor"
                        lesson.progress = 0.0
                        lesson.download_speed = 0.0
                        lesson.eta_seconds = 0.0
                        self.sink.emit("lesson_update", asdict(lesson))
                self.store.save()
                self.sink.emit("job_cancelled", str(exc))
            except Exception as exc:
                self._report_error(exc)
            finally:
                self.active_engine = None

        self._start(job)

    def transcribe(self, key: str, model_size: str = "") -> None:
        if self.busy:
            raise RuntimeError("Başka bir işlem hâlâ çalışıyor.")
        lesson = self.store.lessons.get(key)
        if lesson is None or not lesson.output_path or not Path(lesson.output_path).is_file():
            raise RuntimeError("Transkript için önce ders videosunu indirin.")
        self.current_job_type = "transcript"
        self.job_label = "Transkript hazırlanıyor"
        self.job_title = lesson.title
        self.progress_done = 0
        self.progress_total = 1

        def job() -> None:
            self.sink.emit("job_started", "Transkript hazırlanıyor")
            try:
                from study_tools import generate_quiz, save_quiz, transcribe_video

                assets = Path(self.store.settings.output_dir).expanduser() / "EchoWraith Verileri" / lesson.key

                def on_progress(payload: dict[str, Any]) -> None:
                    self.sink.emit("transcript_progress", {"key": key, **payload})
                    self.sink.emit("status", payload.get("message", "Transkript hazırlanıyor…"))

                json_path, text_path, rows = transcribe_video(
                    Path(lesson.output_path),
                    assets,
                    model_size=model_size or self.store.settings.transcript_model,
                    duration=lesson.duration,
                    stop_event=self.stop_event,
                    progress=on_progress,
                )
                lesson.transcript_json_path = str(json_path)
                lesson.transcript_path = str(text_path)
                try:
                    questions = generate_quiz(rows, lesson.title, 10)
                    lesson.quiz_path = str(save_quiz(questions, assets))
                except Exception as quiz_error:
                    self.sink.log(
                        "Transkript hazır ancak otomatik test daha sonra üretilecek.",
                        "warning",
                        stage="QUIZ",
                        code="QUIZ_DEFERRED",
                        details=str(quiz_error),
                        lesson_key=key,
                    )
                self.store.lessons[key] = lesson
                self.store.save()
                self.progress_done = 1
                self.sink.emit("lesson_update", asdict(lesson))
                self.sink.emit("transcript_ready", {"key": key, "segments": len(rows)})
                self.sink.emit("job_done", "Transkript ve çalışma testi hazır")
            except CancelledError as exc:
                self.sink.emit("job_cancelled", str(exc))
            except Exception as exc:
                if self.stop_event.is_set():
                    self.sink.emit("job_cancelled", "Transkript işlemi kullanıcı tarafından durduruldu.")
                else:
                    self._report_error(exc)

        self._start(job)

    def generate_test(self, key: str, count: int = 10) -> list[dict[str, Any]]:
        if self.busy:
            raise RuntimeError("Aktif işlem bitmeden yeni test oluşturulamaz.")
        from study_tools import generate_quiz, load_transcript, save_quiz

        lesson = self.store.lessons.get(key)
        if lesson is None or not lesson.transcript_json_path:
            raise RuntimeError("Önce bu ders için transkript oluşturun.")
        rows = load_transcript(Path(lesson.transcript_json_path))
        questions = generate_quiz(rows, lesson.title, count)
        assets = Path(self.store.settings.output_dir).expanduser() / "EchoWraith Verileri" / lesson.key
        lesson.quiz_path = str(save_quiz(questions, assets))
        self.store.save()
        self.sink.log(f"{len(questions)} soruluk test üretildi.", "success", stage="QUIZ", code="QUIZ_READY", lesson_key=key)
        return questions

    def delete_lessons(self, keys: list[str], *, remove_records: bool = False) -> dict[str, int]:
        if self.busy:
            raise RuntimeError("Aktif işlem bitmeden dosya silinemez.")
        output_root = Path(self.store.settings.output_dir).expanduser().resolve()
        removed_files = 0
        removed_records = 0
        with self.store.lock:
            for key in keys:
                lesson = self.store.lessons.get(key)
                if lesson is None:
                    continue
                candidates = [
                    lesson.output_path,
                    lesson.webcam_path,
                    lesson.chat_path,
                    lesson.chat_json_path,
                    lesson.thumbnail_path,
                    lesson.transcript_path,
                    lesson.transcript_json_path,
                    lesson.quiz_path,
                ]
                for raw in candidates:
                    if not raw:
                        continue
                    try:
                        path = Path(raw).expanduser().resolve()
                        if path.is_relative_to(output_root) and path.is_file():
                            path.unlink()
                            removed_files += 1
                    except (OSError, ValueError):
                        continue
                assets = output_root / "EchoWraith Verileri" / key
                if assets.is_dir():
                    shutil.rmtree(assets, ignore_errors=True)
                if remove_records:
                    self.store.lessons.pop(key, None)
                    removed_records += 1
                else:
                    lesson.status = "Bekliyor"
                    lesson.progress = 0.0
                    lesson.output_path = ""
                    lesson.webcam_path = ""
                    lesson.chat_path = ""
                    lesson.chat_json_path = ""
                    lesson.thumbnail_path = ""
                    lesson.transcript_path = ""
                    lesson.transcript_json_path = ""
                    lesson.quiz_path = ""
                    lesson.bytes_downloaded = 0
                    lesson.download_speed = 0.0
                    lesson.eta_seconds = 0.0
                self.sink.emit("lesson_update", asdict(lesson) if not remove_records else {"key": key, "deleted": True})
            self.store.save()
        self.sink.log(
            f"{removed_files} yerel dosya silindi; {removed_records} kayıt listeden kaldırıldı.",
            "success",
            stage="DELETE",
            code="DELETE_DONE",
        )
        return {"files": removed_files, "records": removed_records}

    def pause(self) -> bool:
        if self.pause_event.is_set():
            self.pause_event.clear()
            self.sink.emit("status", "Duraklatıldı (aktif dönüştürme bitince bekler)")
            return True
        self.pause_event.set()
        self.sink.emit("status", "Devam ediyor…")
        return False

    def cancel(self) -> None:
        self.stop_event.set()
        self.pause_event.set()
        engine = self.active_engine
        if engine is not None:
            engine.cancel()
        self.sink.emit("status", "Durduruluyor…")

    def shutdown(self, timeout: float = 12.0) -> None:
        """Cancel active work and wait briefly so cleanup/state repair runs."""
        if self.busy:
            self.cancel()
            thread = self.thread
            if thread is not None and thread is not threading.current_thread():
                thread.join(timeout=max(0.0, timeout))

    def _report_error(self, exc: Exception) -> None:
        diagnosis = self.sink.exception("JOB", exc)
        self.sink.emit("job_error", {"message": diagnosis["reason"], "suggestion": diagnosis["suggestion"], "code": diagnosis["code"]})


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        ensure_dirs()
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        self.title(f"{APP_NAME} {APP_VERSION}")
        self.geometry("1320x860")
        self.minsize(1080, 700)
        self.configure(fg_color=PALETTE["bg"])
        self.events: queue.Queue[tuple[str, Any]] = queue.Queue()
        self.store = StateStore()
        self.worker = WorkerController(self.store, self.events)
        self.authenticated = False
        self.current_item_key = ""
        self.tree_items: dict[str, str] = {}
        self._build_style()
        self._build_ui()
        self._refresh_tree()
        self.after(100, self._poll_events)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_style(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure(
            "Lessons.Treeview",
            background=PALETTE["panel"],
            fieldbackground=PALETTE["panel"],
            foreground=PALETTE["text"],
            rowheight=34,
            borderwidth=0,
            font=("Segoe UI", 10),
        )
        style.configure(
            "Lessons.Treeview.Heading",
            background=PALETTE["panel_alt"],
            foreground=PALETTE["muted"],
            relief="flat",
            font=("Segoe UI Semibold", 10),
        )
        style.map("Lessons.Treeview", background=[("selected", "#173d60")], foreground=[("selected", "#ffffff")])
        style.map("Lessons.Treeview.Heading", background=[("active", PALETTE["panel_alt"])])

    def _build_ui(self) -> None:
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        sidebar = ctk.CTkFrame(self, width=235, corner_radius=0, fg_color="#0a1626")
        sidebar.grid(row=0, column=0, sticky="nsew")
        sidebar.grid_propagate(False)
        ctk.CTkLabel(sidebar, text="◉", text_color=PALETTE["accent"], font=("Segoe UI", 30, "bold")).pack(pady=(30, 0))
        ctk.CTkLabel(sidebar, text="EFSANE", font=("Segoe UI", 22, "bold"), text_color=PALETTE["text"]).pack()
        ctk.CTkLabel(sidebar, text="DERS İNDİRİCİ", font=("Segoe UI", 11, "bold"), text_color=PALETTE["muted"]).pack(pady=(0, 28))

        self.connection_label = ctk.CTkLabel(
            sidebar,
            text="●  Oturum bekleniyor",
            text_color=PALETTE["yellow"],
            anchor="w",
            font=("Segoe UI", 11, "bold"),
        )
        self.connection_label.pack(fill="x", padx=24, pady=(0, 22))
        self.sidebar_count = ctk.CTkLabel(sidebar, text="0 ders", text_color=PALETTE["muted"], anchor="w")
        self.sidebar_count.pack(fill="x", padx=24, pady=6)
        self.sidebar_done = ctk.CTkLabel(sidebar, text="0 tamamlandı", text_color=PALETTE["green"], anchor="w")
        self.sidebar_done.pack(fill="x", padx=24, pady=6)
        self.sidebar_error = ctk.CTkLabel(sidebar, text="0 hata", text_color=PALETTE["red"], anchor="w")
        self.sidebar_error.pack(fill="x", padx=24, pady=6)
        ctk.CTkLabel(
            sidebar,
            text="Şifre kaydedilmez.\nOturum yerel Chrome\nprofilinde tutulur.",
            justify="left",
            anchor="w",
            text_color="#64748b",
            font=("Segoe UI", 10),
        ).pack(side="bottom", fill="x", padx=24, pady=28)

        main = ctk.CTkFrame(self, corner_radius=0, fg_color=PALETTE["bg"])
        main.grid(row=0, column=1, sticky="nsew")
        main.grid_columnconfigure(0, weight=1)
        main.grid_rowconfigure(3, weight=1)

        header = ctk.CTkFrame(main, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=28, pady=(22, 12))
        header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(header, text="Ders arşivini tek yerden yönet", font=("Segoe UI", 24, "bold"), text_color=PALETTE["text"]).grid(row=0, column=0, sticky="w")
        self.status_label = ctk.CTkLabel(header, text="Hazır", text_color=PALETTE["muted"], font=("Segoe UI", 11))
        self.status_label.grid(row=1, column=0, sticky="w", pady=(4, 0))
        ctk.CTkButton(
            header,
            text="Klasörü Aç",
            width=110,
            fg_color=PALETTE["panel_alt"],
            hover_color=PALETTE["border"],
            command=self._open_output,
        ).grid(row=0, column=1, rowspan=2, padx=(12, 0))

        auth = ctk.CTkFrame(main, fg_color=PALETTE["panel"], border_color=PALETTE["border"], border_width=1, corner_radius=12)
        auth.grid(row=1, column=0, sticky="ew", padx=28, pady=(0, 12))
        auth.grid_columnconfigure(0, weight=1)
        auth.grid_columnconfigure(1, weight=1)
        self.email_entry = ctk.CTkEntry(auth, placeholder_text="Öğrenci e-postası (ilk girişte)", height=38, border_color=PALETTE["border"])
        self.email_entry.grid(row=0, column=0, sticky="ew", padx=(14, 7), pady=14)
        self.password_entry = ctk.CTkEntry(auth, placeholder_text="Şifre (kaydedilmez)", show="●", height=38, border_color=PALETTE["border"])
        self.password_entry.grid(row=0, column=1, sticky="ew", padx=7, pady=14)
        self.login_button = ctk.CTkButton(auth, text="Oturumu Aç", width=124, height=38, command=self._login)
        self.login_button.grid(row=0, column=2, padx=(7, 14), pady=14)

        controls = ctk.CTkFrame(main, fg_color=PALETTE["panel"], border_color=PALETTE["border"], border_width=1, corner_radius=12)
        controls.grid(row=2, column=0, sticky="ew", padx=28, pady=(0, 12))
        controls.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(controls, text="Kayıt klasörü", text_color=PALETTE["muted"]).grid(row=0, column=0, padx=(14, 8), pady=(12, 6), sticky="w")
        self.output_entry = ctk.CTkEntry(controls, height=34, border_color=PALETTE["border"])
        self.output_entry.insert(0, self.store.settings.output_dir)
        self.output_entry.grid(row=0, column=1, sticky="ew", padx=8, pady=(12, 6))
        ctk.CTkButton(controls, text="Seç", width=70, height=34, fg_color=PALETTE["panel_alt"], command=self._choose_output).grid(row=0, column=2, padx=(8, 14), pady=(12, 6))

        action_row = ctk.CTkFrame(controls, fg_color="transparent")
        action_row.grid(row=1, column=0, columnspan=3, sticky="ew", padx=14, pady=(6, 12))
        action_row.grid_columnconfigure(7, weight=1)
        self.scan_button = ctk.CTkButton(action_row, text="1  Dersleri Tara", width=138, command=self._scan)
        self.scan_button.grid(row=0, column=0, padx=(0, 8))
        self.download_button = ctk.CTkButton(
            action_row,
            text="2  Seçilenleri İndir",
            width=166,
            fg_color="#157f55",
            hover_color="#106442",
            command=self._download,
        )
        self.download_button.grid(row=0, column=1, padx=8)
        self.pause_button = ctk.CTkButton(action_row, text="Duraklat", width=92, fg_color=PALETTE["panel_alt"], command=self._pause)
        self.pause_button.grid(row=0, column=2, padx=8)
        self.cancel_button = ctk.CTkButton(action_row, text="Durdur", width=82, fg_color="#7f2d35", hover_color="#632129", command=self._cancel)
        self.cancel_button.grid(row=0, column=3, padx=8)
        self.chat_switch = ctk.CTkSwitch(action_row, text="Sohbeti kaydet", progress_color=PALETTE["accent"])
        if self.store.settings.save_chat:
            self.chat_switch.select()
        self.chat_switch.grid(row=0, column=4, padx=(20, 8))
        self.quality_menu = ctk.CTkOptionMenu(action_row, values=["Hızlı (720p)", "Dengeli (720p)", "Yüksek (1080p)"], width=142)
        self.quality_menu.set(self.store.settings.quality)
        self.quality_menu.grid(row=0, column=5, padx=8)
        self.encoder_menu = ctk.CTkOptionMenu(action_row, values=["libx264 (uyumlu)", "NVIDIA NVENC", "Intel Quick Sync", "AMD AMF"], width=150)
        self.encoder_menu.set(self.store.settings.encoder)
        self.encoder_menu.grid(row=0, column=6, padx=8)

        content = ctk.CTkFrame(main, fg_color=PALETTE["panel"], border_color=PALETTE["border"], border_width=1, corner_radius=12)
        content.grid(row=3, column=0, sticky="nsew", padx=28, pady=(0, 18))
        content.grid_columnconfigure(0, weight=1)
        content.grid_rowconfigure(1, weight=1)
        content.grid_rowconfigure(4, weight=0)

        filters = ctk.CTkFrame(content, fg_color="transparent")
        filters.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 8))
        filters.grid_columnconfigure(2, weight=1)
        ctk.CTkButton(filters, text="Tümünü Seç", width=92, height=30, fg_color=PALETTE["panel_alt"], command=lambda: self._select_all(True)).grid(row=0, column=0, padx=(0, 6))
        ctk.CTkButton(filters, text="Seçimi Kaldır", width=105, height=30, fg_color=PALETTE["panel_alt"], command=lambda: self._select_all(False)).grid(row=0, column=1, padx=6)
        self.search_var = ctk.StringVar()
        self.search_var.trace_add("write", lambda *_: self._refresh_tree())
        self.search_entry = ctk.CTkEntry(filters, textvariable=self.search_var, placeholder_text="Ders ara…", height=32)
        self.search_entry.grid(row=0, column=2, sticky="e", padx=6)
        self.filter_menu = ctk.CTkOptionMenu(filters, values=["Tümü", "Seçili", "Bekliyor", "BBB / TUES", "Zoom", "Tamamlandı", "Hata"], width=125, command=lambda _v: self._refresh_tree())
        self.filter_menu.grid(row=0, column=3, padx=(6, 0))

        tree_frame = ctk.CTkFrame(content, fg_color=PALETTE["panel"], corner_radius=0)
        tree_frame.grid(row=1, column=0, sticky="nsew", padx=12)
        tree_frame.grid_columnconfigure(0, weight=1)
        tree_frame.grid_rowconfigure(0, weight=1)
        columns = ("pick", "date", "title", "type", "size", "status")
        self.tree = ttk.Treeview(tree_frame, columns=columns, show="headings", style="Lessons.Treeview", selectmode="browse")
        headings = {"pick": "", "date": "Tarih", "title": "Ders", "type": "Tür", "size": "Boyut", "status": "Durum"}
        widths = {"pick": 42, "date": 95, "title": 520, "type": 120, "size": 85, "status": 140}
        for key in columns:
            self.tree.heading(key, text=headings[key])
            self.tree.column(key, width=widths[key], minwidth=widths[key] if key != "title" else 260, stretch=key == "title")
        scroll = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        scroll.grid(row=0, column=1, sticky="ns")
        self.tree.bind("<Button-1>", self._tree_click)
        self.tree.bind("<Double-1>", self._open_selected_file)
        self.tree.tag_configure("done", foreground="#75e0aa")
        self.tree.tag_configure("error", foreground="#ff8a82")
        self.tree.tag_configure("active", foreground="#7cc9ff")

        progress_frame = ctk.CTkFrame(content, fg_color="transparent")
        progress_frame.grid(row=2, column=0, sticky="ew", padx=12, pady=(10, 4))
        progress_frame.grid_columnconfigure(0, weight=1)
        self.overall_progress = ctk.CTkProgressBar(progress_frame, height=8, progress_color=PALETTE["accent"])
        self.overall_progress.set(0)
        self.overall_progress.grid(row=0, column=0, sticky="ew")
        self.progress_label = ctk.CTkLabel(progress_frame, text="0 / 0", width=80, text_color=PALETTE["muted"])
        self.progress_label.grid(row=0, column=1, padx=(10, 0))

        self.log_box = ctk.CTkTextbox(content, height=105, fg_color="#0a1524", border_color=PALETTE["border"], border_width=1, font=("Cascadia Mono", 10))
        self.log_box.grid(row=4, column=0, sticky="ew", padx=12, pady=(7, 12))
        self.log_box.configure(state="disabled")

    def _credentials(self) -> tuple[str, str]:
        return self.email_entry.get().strip(), self.password_entry.get()

    def _sync_settings(self) -> None:
        output = self.output_entry.get().strip()
        if output:
            self.store.settings.output_dir = output
        self.store.settings.save_chat = bool(self.chat_switch.get())
        self.store.settings.quality = self.quality_menu.get()
        self.store.settings.encoder = self.encoder_menu.get()
        self.store.save()

    def _login(self) -> None:
        if self._guard_busy():
            return
        email, password = self._credentials()
        self.worker.authenticate(email, password)

    def _scan(self) -> None:
        if self._guard_busy():
            return
        self._sync_settings()
        self.worker.scan(*self._credentials())

    def _download(self) -> None:
        if self._guard_busy():
            return
        self._sync_settings()
        keys = [key for key, item in self.store.lessons.items() if item.selected]
        if not keys:
            messagebox.showinfo(APP_NAME, "Önce en az bir ders seç.")
            return
        self.worker.download(keys, *self._credentials())

    def _pause(self) -> None:
        if not self.worker.busy:
            return
        paused = self.worker.pause()
        self.pause_button.configure(text="Devam Et" if paused else "Duraklat")

    def _cancel(self) -> None:
        if self.worker.busy:
            self.worker.cancel()

    def _guard_busy(self) -> bool:
        if self.worker.busy:
            messagebox.showinfo(APP_NAME, "Mevcut işlem tamamlanmadan yeni işlem başlatılamaz.")
            return True
        return False

    def _choose_output(self) -> None:
        chosen = filedialog.askdirectory(initialdir=self.output_entry.get() or str(Path.home()))
        if chosen:
            self.output_entry.delete(0, "end")
            self.output_entry.insert(0, chosen)
            self._sync_settings()

    def _open_output(self) -> None:
        path = Path(self.output_entry.get().strip() or self.store.settings.output_dir).expanduser()
        path.mkdir(parents=True, exist_ok=True)
        if os.name == "nt":
            os.startfile(path)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])

    def _open_selected_file(self, _event=None) -> None:
        selection = self.tree.selection()
        if not selection:
            return
        key = self.tree.item(selection[0], "tags")
        lesson_key_value = key[-1] if key else ""
        lesson = self.store.lessons.get(lesson_key_value)
        if lesson and lesson.output_path and Path(lesson.output_path).exists():
            webbrowser.open(Path(lesson.output_path).as_uri())

    def _tree_click(self, event) -> None:
        if self.tree.identify_region(event.x, event.y) != "cell" or self.tree.identify_column(event.x) != "#1":
            return
        row_id = self.tree.identify_row(event.y)
        if not row_id:
            return
        tags = self.tree.item(row_id, "tags")
        key = tags[-1] if tags else ""
        lesson = self.store.lessons.get(key)
        if lesson:
            lesson.selected = not lesson.selected
            self.store.save()
            self._refresh_tree()

    def _select_all(self, value: bool) -> None:
        for lesson in self.store.lessons.values():
            lesson.selected = value
        self.store.save()
        self._refresh_tree()

    def _visible_lessons(self) -> list[Lesson]:
        search = self.search_var.get().strip().lower() if hasattr(self, "search_var") else ""
        chosen_filter = self.filter_menu.get() if hasattr(self, "filter_menu") else "Tümü"
        values = list(self.store.lessons.values())
        if search:
            values = [item for item in values if search in f"{item.title} {item.date} {item.source_type} {item.status}".lower()]
        if chosen_filter == "Seçili":
            values = [item for item in values if item.selected]
        elif chosen_filter == "Bekliyor":
            values = [item for item in values if item.status in {"Bekliyor", "Kaynak aranıyor", "İndiriliyor", "Birleştiriliyor"}]
        elif chosen_filter in {"BBB / TUES", "Zoom"}:
            values = [item for item in values if item.source_type == chosen_filter]
        elif chosen_filter in {"Tamamlandı", "Hata"}:
            values = [item for item in values if item.status == chosen_filter]
        return values

    def _refresh_tree(self) -> None:
        if not hasattr(self, "tree"):
            return
        selected_iid = self.tree.selection()[0] if self.tree.selection() else None
        self.tree.delete(*self.tree.get_children())
        self.tree_items.clear()
        for lesson in self._visible_lessons():
            tag = "done" if lesson.status == "Tamamlandı" else "error" if lesson.status == "Hata" else "active" if lesson.status not in {"Bekliyor"} else ""
            tags = tuple(item for item in (tag, lesson.key) if item)
            status = lesson.status
            if lesson.status in {"İndiriliyor", "Birleştiriliyor"} and lesson.progress:
                status = f"{lesson.status} %{lesson.progress * 100:.0f}"
            iid = self.tree.insert(
                "",
                "end",
                values=("☑" if lesson.selected else "☐", lesson.date, lesson.title, lesson.source_type, human_bytes(lesson.known_size), status),
                tags=tags,
            )
            self.tree_items[lesson.key] = iid
        if selected_iid and self.tree.exists(selected_iid):
            self.tree.selection_set(selected_iid)
        total = len(self.store.lessons)
        done = sum(item.status == "Tamamlandı" for item in self.store.lessons.values())
        errors = sum(item.status == "Hata" for item in self.store.lessons.values())
        self.sidebar_count.configure(text=f"{total} ders")
        self.sidebar_done.configure(text=f"{done} tamamlandı")
        self.sidebar_error.configure(text=f"{errors} hata")

    def _set_busy(self, busy: bool) -> None:
        state = "disabled" if busy else "normal"
        for button in (self.login_button, self.scan_button, self.download_button):
            button.configure(state=state)
        self.pause_button.configure(state="normal" if busy else "disabled")
        self.cancel_button.configure(state="normal" if busy else "disabled")
        if not busy:
            self.pause_button.configure(text="Duraklat")

    def _append_log(self, payload: dict[str, str]) -> None:
        self.log_box.configure(state="normal")
        self.log_box.insert("end", f"[{payload.get('time', now_text())}] {payload.get('message', '')}\n")
        lines = int(self.log_box.index("end-1c").split(".")[0])
        if lines > 700:
            self.log_box.delete("1.0", "120.0")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def _poll_events(self) -> None:
        try:
            while True:
                kind, payload = self.events.get_nowait()
                if kind == "log":
                    self._append_log(payload)
                elif kind == "status":
                    self.status_label.configure(text=str(payload))
                elif kind == "auth_ok":
                    self.authenticated = True
                    self.password_entry.delete(0, "end")
                    self.connection_label.configure(text="●  Oturum hazır", text_color=PALETTE["green"])
                elif kind == "needs_login":
                    self.connection_label.configure(text="●  Tarayıcıda giriş bekleniyor", text_color=PALETTE["yellow"])
                elif kind == "job_started":
                    self._set_busy(True)
                    self.status_label.configure(text=str(payload))
                elif kind == "job_done":
                    self._set_busy(False)
                    self.status_label.configure(text=str(payload))
                    self._refresh_tree()
                elif kind == "job_cancelled":
                    self._set_busy(False)
                    self.status_label.configure(text=str(payload))
                    self._refresh_tree()
                elif kind == "job_error":
                    self._set_busy(False)
                    self.status_label.configure(text=f"Hata: {payload['message']}")
                    messagebox.showerror(APP_NAME, payload["message"])
                elif kind == "scan_progress":
                    self.status_label.configure(text=f"Sayfa {payload['page']} · {payload['count']} ders bulundu")
                elif kind == "scan_complete":
                    self._refresh_tree()
                elif kind == "lesson_update":
                    lesson = Lesson.from_dict(payload)
                    self.store.lessons[lesson.key] = lesson
                    self._refresh_tree()
                elif kind == "item_progress":
                    key = payload["key"]
                    lesson = self.store.lessons.get(key)
                    if lesson:
                        lesson.progress = payload.get("progress", 0.0)
                        self.current_item_key = key
                        self._refresh_tree()
                elif kind == "overall_progress":
                    done, total = payload["done"], payload["total"]
                    self.overall_progress.set(done / total if total else 0)
                    self.progress_label.configure(text=f"{done} / {total}")
        except queue.Empty:
            pass
        self.after(100, self._poll_events)

    def _on_close(self) -> None:
        if self.worker.busy and not messagebox.askyesno(APP_NAME, "İşlem sürüyor. Uygulamayı kapatmak istiyor musun?"):
            return
        self.worker.cancel()
        self._sync_settings()
        self.destroy()


def main() -> int:
    if sys.version_info < (3, 10):
        raise SystemExit("Python 3.10 veya daha yeni bir sürüm gerekli.")
    ensure_dirs()
    app = App()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
