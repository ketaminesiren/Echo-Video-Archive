from __future__ import annotations

import atexit
import json
import mimetypes
import os
import re
import socket
import subprocess
import sys
import threading
import time
import uuid
import webbrowser
from dataclasses import asdict
from datetime import datetime, timezone
from email.utils import formatdate
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit

import requests

import echowraith_core as core
import updater
from diagnostics import sanitize
from study_tools import load_quiz, load_transcript


HOST = "127.0.0.1"
PREFERRED_PORT = 8765
WEB_ROOT = Path(__file__).resolve().parent / "web"

STORE = core.StateStore()
BROKER = core.EventBroker()
WORKER = core.WorkerController(STORE, BROKER)
LAST_CLIENT_SEEN = time.monotonic()
# Set when the panel tab reports it is closing (pagehide beacon). While set and
# no other client checks in, the app shuts itself down quickly instead of
# lingering in the background eating memory.
CLIENT_LEFT_AT: "float | None" = None
SERVER_INSTANCE: "EchoWraithHTTPServer | None" = None


def category_for(title: str) -> str:
    lower = title.casefold()
    rules = (
        (("gelişim", "psikoloji"), "Gelişim Psikolojisi"),
        (("çocuk hak",), "Çocuk Hakları"),
        (("drama",), "Drama"),
        (("sözel mantık", "mantık"), "Sözel Mantık"),
        (("anne baba",), "Anne Baba Eğitimi"),
        (("yöntem", "program"), "Yöntem ve Programlar"),
        (("rehberlik", "koçluk"), "Rehberlik ve Koçluk"),
        (("çocuk edebiyat",), "Çocuk Edebiyatı"),
        (("meb", "ags"), "MEB AGS"),
    )
    for needles, label in rules:
        if any(needle in lower for needle in needles):
            return label
    return "ÖABT Dersleri"


def path_exists(value: str) -> bool:
    try:
        return bool(value and Path(value).expanduser().is_file())
    except OSError:
        return False


def serialize_lesson(lesson: core.Lesson) -> dict[str, Any]:
    data = asdict(lesson)
    output_exists = path_exists(lesson.output_path)
    webcam_exists = path_exists(lesson.webcam_path)
    chat_exists = path_exists(lesson.chat_json_path) or path_exists(lesson.chat_path)
    thumbnail_exists = path_exists(lesson.thumbnail_path)
    transcript_exists = path_exists(lesson.transcript_json_path) or path_exists(lesson.transcript_path)
    quiz_exists = path_exists(lesson.quiz_path)
    year_match = re.search(r"20\d{2}", lesson.date or lesson.title)
    data.update(
        {
            "category": category_for(lesson.title),
            "year": year_match.group(0) if year_match else "",
            "has_webcam": webcam_exists,
            "has_chat": chat_exists,
            "media_url": f"/api/media/{lesson.key}" if output_exists else "",
            "webcam_url": f"/api/webcam/{lesson.key}" if webcam_exists else "",
            "thumbnail_url": f"/api/thumbnail/{lesson.key}" if thumbnail_exists else "",
            "has_transcript": transcript_exists,
            "has_quiz": quiz_exists,
            "output_exists": output_exists,
        }
    )
    for private_key in (
        "source_url",
        "href",
        "locator_hint",
        "meeting_id",
        "chat_json_path",
        "chat_path",
        "webcam_path",
        "thumbnail_path",
        "transcript_path",
        "transcript_json_path",
        "quiz_path",
    ):
        data.pop(private_key, None)
    return data


def job_state() -> dict[str, Any]:
    return {
        "busy": WORKER.busy,
        "stopping": WORKER.stopping,
        "paused": WORKER.busy and not WORKER.pause_event.is_set(),
        "label": WORKER.job_label,
        "title": WORKER.job_title,
        "detail": BROKER.last_status,
        "done": WORKER.progress_done,
        "total": WORKER.progress_total,
        "type": WORKER.current_job_type,
    }


def storage_state() -> dict[str, int]:
    output = Path(STORE.settings.output_dir).expanduser()
    output.mkdir(parents=True, exist_ok=True)
    usage = core.shutil.disk_usage(output)
    return {"total": usage.total, "free": usage.free, "used": usage.used}


def state_payload() -> dict[str, Any]:
    with STORE.lock:
        lessons = [serialize_lesson(lesson) for lesson in STORE.lessons.values()]
        settings = asdict(STORE.settings)
    return {
        "version": core.APP_VERSION,
        "authenticated": BROKER.authenticated,
        "profile": STORE.profile,
        "team": core.APP_TEAM,
        "settings": settings,
        "storage": storage_state(),
        "job": job_state(),
        "lessons": lessons,
    }


def diagnostic_state_summary() -> dict[str, Any]:
    with STORE.lock:
        lessons = [
            {
                "key": lesson.key,
                "title": lesson.title,
                "date": lesson.date,
                "status": lesson.status,
                "source_type": lesson.source_type,
                "progress": lesson.progress,
                "attempts": lesson.attempts,
                "recovery_count": lesson.recovery_count,
                "error": lesson.error,
                "output_exists": path_exists(lesson.output_path),
                "has_webcam": path_exists(lesson.webcam_path),
                "has_chat": path_exists(lesson.chat_json_path) or path_exists(lesson.chat_path),
                "has_transcript": path_exists(lesson.transcript_json_path),
            }
            for lesson in STORE.lessons.values()
        ]
        settings = asdict(STORE.settings)
        settings["output_dir"] = "[YEREL KLASÖR GİZLENDİ]"
    return sanitize({"settings": settings, "job": job_state(), "lessons": lessons, "profile_present": bool(STORE.profile)})


def lesson_or_error(key: str) -> core.Lesson:
    lesson = STORE.lessons.get(key)
    if lesson is None:
        raise KeyError("Ders bulunamadı.")
    return lesson


def load_chat_messages(lesson: core.Lesson) -> list[dict[str, Any]]:
    if path_exists(lesson.chat_json_path):
        try:
            data = json.loads(Path(lesson.chat_json_path).read_text(encoding="utf-8"))
            if isinstance(data, list):
                return [item for item in data if isinstance(item, dict)]
        except (OSError, json.JSONDecodeError):
            pass
    if not path_exists(lesson.chat_path):
        return []
    messages: list[dict[str, Any]] = []
    pattern = re.compile(r"^\[(?:(\d{1,2}):)?(\d{1,2}):(\d{2})(?:\.\d+)?\]\s*([^:]{1,100}):\s*(.*)$")
    try:
        lines = Path(lesson.chat_path).read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    for line in lines:
        match = pattern.match(line.strip())
        if not match:
            continue
        sender = match.group(4).strip()
        seconds = int(match.group(1) or 0) * 3600 + int(match.group(2)) * 60 + int(match.group(3))
        messages.append(
            {
                "time": seconds,
                "sender": sender,
                "text": match.group(5).strip(),
                "teacher": any(token in sender.casefold() for token in ("öğretmen", "hoca", "teacher")),
            }
        )
    return messages


def open_path(path: Path) -> None:
    path = path.expanduser().resolve()
    if os.name == "nt":
        os.startfile(path)  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path)])


class EchoWraithHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


class EchoWraithHandler(BaseHTTPRequestHandler):
    server_version = f"EchoWraith/{core.APP_VERSION}"
    protocol_version = "HTTP/1.1"
    max_body_size = 1024 * 1024

    def log_message(self, format_string: str, *args: Any) -> None:
        if self.command and self.path.startswith("/api/") and not self.path.startswith("/api/events"):
            core.EventSink(BROKER).log(format_string % args, "debug", stage="HTTP")

    def _common_headers(self, content_type: str, length: int, cache: str = "no-store") -> None:
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(length))
        self.send_header("Cache-Control", cache)
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Frame-Options", "SAMEORIGIN")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; img-src 'self' data:; media-src 'self'; "
            "script-src 'self'; style-src 'self' 'unsafe-inline'; connect-src 'self'; frame-ancestors 'self'",
        )

    def _json(self, payload: Any, status: int = 200, head_only: bool = False) -> None:
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self._common_headers("application/json; charset=utf-8", len(body))
        self.end_headers()
        if not head_only:
            self.wfile.write(body)

    def _read_json(self) -> dict[str, Any]:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as exc:
            raise ValueError("Geçersiz istek uzunluğu.") from exc
        if length < 0 or length > self.max_body_size:
            raise ValueError("İstek gövdesi çok büyük.")
        if not length:
            return {}
        try:
            value = json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("Geçersiz JSON isteği.") from exc
        if not isinstance(value, dict):
            raise ValueError("JSON nesnesi bekleniyordu.")
        return value

    def _static(self, asset: str, head_only: bool = False) -> None:
        filename = "index.html" if asset in {"", "/"} else asset.lstrip("/")
        path = (WEB_ROOT / filename).resolve()
        try:
            allowed = path.is_relative_to(WEB_ROOT.resolve())
        except AttributeError:
            allowed = str(path).startswith(str(WEB_ROOT.resolve()) + os.sep)
        allowed_suffixes = {".html", ".css", ".js", ".json", ".png", ".jpg", ".jpeg", ".webp", ".svg", ".ico"}
        if not allowed or path.suffix.lower() not in allowed_suffixes:
            self._json({"error": "Dosya bulunamadı."}, 404, head_only)
            return
        if not path.is_file():
            self._json({"error": "Web paneli dosyası eksik."}, 500, head_only)
            return
        body = path.read_bytes()
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        if content_type.startswith("text/") or content_type in {"application/javascript", "application/json"}:
            content_type += "; charset=utf-8"
        self.send_response(200)
        self._common_headers(content_type, len(body), "no-cache")
        self.send_header("Last-Modified", formatdate(path.stat().st_mtime, usegmt=True))
        self.end_headers()
        if not head_only:
            self.wfile.write(body)

    def _media(self, path_value: str, head_only: bool = False) -> None:
        path = Path(path_value).expanduser().resolve()
        output_root = Path(STORE.settings.output_dir).expanduser().resolve()
        try:
            allowed = path.is_relative_to(output_root)
        except AttributeError:
            allowed = str(path).startswith(str(output_root) + os.sep)
        if not allowed or not path.is_file():
            self._json({"error": "Medya dosyası bulunamadı."}, 404, head_only)
            return
        size = path.stat().st_size
        start, end = 0, max(0, size - 1)
        status = HTTPStatus.OK
        range_header = self.headers.get("Range", "")
        if range_header:
            match = re.fullmatch(r"bytes=(\d*)-(\d*)", range_header.strip())
            if not match:
                self.send_response(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
                self.send_header("Content-Range", f"bytes */{size}")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            if match.group(1):
                start = int(match.group(1))
                end = int(match.group(2)) if match.group(2) else end
            elif match.group(2):
                suffix = int(match.group(2))
                start = max(0, size - suffix)
            if start >= size or end < start:
                self.send_response(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
                self.send_header("Content-Range", f"bytes */{size}")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            end = min(end, size - 1)
            status = HTTPStatus.PARTIAL_CONTENT
        length = end - start + 1
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        self.send_response(status)
        self._common_headers(content_type, length, "private, max-age=0")
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Last-Modified", formatdate(path.stat().st_mtime, usegmt=True))
        if status == HTTPStatus.PARTIAL_CONTENT:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.end_headers()
        if head_only:
            return
        with path.open("rb") as handle:
            handle.seek(start)
            remaining = length
            while remaining:
                chunk = handle.read(min(1024 * 1024, remaining))
                if not chunk:
                    break
                self.wfile.write(chunk)
                remaining -= len(chunk)

    def _send_file(self, path: Path, *, download_name: str = "", head_only: bool = False) -> None:
        if not path.is_file():
            self._json({"error": "Dosya bulunamadı."}, 404, head_only)
            return
        body_length = path.stat().st_size
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        self.send_response(200)
        self._common_headers(content_type, body_length, "no-store")
        if download_name:
            safe_name = re.sub(r"[^A-Za-z0-9._-]", "-", download_name)
            self.send_header("Content-Disposition", f'attachment; filename="{safe_name}"')
        self.end_headers()
        if head_only:
            return
        with path.open("rb") as handle:
            while chunk := handle.read(1024 * 1024):
                self.wfile.write(chunk)

    def _api_get(self, path: str, query: str, head_only: bool = False) -> bool:
        global LAST_CLIENT_SEEN, CLIENT_LEFT_AT
        LAST_CLIENT_SEEN = time.monotonic()
        # Any live request means a panel is open again; cancel a pending
        # auto-close (e.g. the tab was only refreshed, or another tab is active).
        CLIENT_LEFT_AT = None
        if path == "/api/health":
            self._json({"ok": True, "app": core.APP_NAME, "version": core.APP_VERSION, "team": core.APP_TEAM}, head_only=head_only)
            return True
        if path == "/api/heartbeat":
            self._json({"ok": True, "busy": WORKER.busy}, head_only=head_only)
            return True
        if path == "/api/state":
            self._json(state_payload(), head_only=head_only)
            return True
        if path == "/api/events":
            match = re.search(r"(?:^|&)since=(\d+)", query)
            since = int(match.group(1)) if match else 0
            items, newest = BROKER.read_since(since, timeout=20.0 if not head_only else 0.0)
            self._json({"events": items, "last_id": newest}, head_only=head_only)
            return True
        if path == "/api/update/check":
            self._json(updater.check_update(), head_only=head_only)
            return True
        if path == "/api/logs":
            match = re.search(r"(?:^|&)limit=(\d+)", query)
            limit = int(match.group(1)) if match else 300
            self._json({"entries": core.DIAGNOSTICS.recent(limit)}, head_only=head_only)
            return True
        if path == "/api/diagnostics/bundle":
            stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            target = core.LOG_DIR / f"EchoWraith-Tanilama-{stamp}.zip"
            core.DIAGNOSTICS.make_bundle(target, diagnostic_state_summary(), {"authenticated": BROKER.authenticated})
            self._send_file(target, download_name=target.name, head_only=head_only)
            return True
        media_match = re.fullmatch(r"/api/(media|webcam|thumbnail)/([^/]+)", path)
        if media_match:
            lesson = lesson_or_error(unquote(media_match.group(2)))
            paths = {"media": lesson.output_path, "webcam": lesson.webcam_path, "thumbnail": lesson.thumbnail_path}
            self._media(paths[media_match.group(1)], head_only)
            return True
        chat_match = re.fullmatch(r"/api/lessons/([^/]+)/chat", path)
        if chat_match:
            self._json({"messages": load_chat_messages(lesson_or_error(unquote(chat_match.group(1))))}, head_only=head_only)
            return True
        transcript_match = re.fullmatch(r"/api/lessons/([^/]+)/transcript", path)
        if transcript_match:
            lesson = lesson_or_error(unquote(transcript_match.group(1)))
            segments = load_transcript(Path(lesson.transcript_json_path)) if path_exists(lesson.transcript_json_path) else []
            self._json({"segments": segments, "ready": bool(segments)}, head_only=head_only)
            return True
        quiz_match = re.fullmatch(r"/api/lessons/([^/]+)/quiz", path)
        if quiz_match:
            lesson = lesson_or_error(unquote(quiz_match.group(1)))
            questions = load_quiz(Path(lesson.quiz_path)) if path_exists(lesson.quiz_path) else []
            self._json({"questions": questions, "ready": bool(questions)}, head_only=head_only)
            return True
        return False

    def _api_mutation(self, method: str, path: str) -> bool:
        data = self._read_json()
        if method == "POST" and path == "/api/auth":
            WORKER.authenticate(str(data.get("email", "")).strip(), str(data.get("password", "")))
            self._json({"started": True}, 202)
            return True
        if method == "POST" and path == "/api/scan":
            WORKER.scan(str(data.get("email", "")).strip(), str(data.get("password", "")))
            self._json({"started": True}, 202)
            return True
        if method == "POST" and path == "/api/download":
            keys = [str(key) for key in data.get("keys", []) if str(key) in STORE.lessons]
            if not keys:
                raise ValueError("İndirilecek ders seçilmedi.")
            WORKER.download(keys, str(data.get("email", "")).strip(), str(data.get("password", "")))
            self._json({"started": True, "count": len(keys)}, 202)
            return True
        transcript_match = re.fullmatch(r"/api/lessons/([^/]+)/transcribe", path)
        if method == "POST" and transcript_match:
            key = unquote(transcript_match.group(1))
            lesson_or_error(key)
            model_size = str(data.get("model", STORE.settings.transcript_model))
            if model_size not in {"tiny", "base", "small"}:
                model_size = "base"
            WORKER.transcribe(key, model_size)
            self._json({"started": True, "key": key}, 202)
            return True
        quiz_match = re.fullmatch(r"/api/lessons/([^/]+)/quiz", path)
        if method == "POST" and quiz_match:
            key = unquote(quiz_match.group(1))
            count = max(3, min(int(data.get("count", 10) or 10), 20))
            questions = WORKER.generate_test(key, count)
            self._json({"questions": questions, "count": len(questions)}, 201)
            return True
        if method == "POST" and path == "/api/delete":
            keys = [str(key) for key in data.get("keys", []) if str(key) in STORE.lessons]
            if not keys:
                raise ValueError("Silinecek ders seçilmedi.")
            result = WORKER.delete_lessons(keys, remove_records=bool(data.get("remove_records", False)))
            self._json({"ok": True, **result})
            return True
        if method == "POST" and path == "/api/pause":
            if not WORKER.busy:
                raise RuntimeError("Aktif işlem yok.")
            self._json({"paused": WORKER.pause()})
            return True
        if method == "POST" and path == "/api/cancel":
            if WORKER.busy:
                WORKER.cancel()
            self._json({"ok": True})
            return True
        if method == "PATCH" and path == "/api/selection":
            keys = {str(key) for key in data.get("keys", [])}
            selected = bool(data.get("selected", True))
            with STORE.lock:
                for key in keys:
                    if key in STORE.lessons:
                        STORE.lessons[key].selected = selected
                STORE.save()
            self._json({"ok": True})
            return True
        if method == "PATCH" and path == "/api/settings":
            allowed_quality = {"Hızlı (720p)", "Dengeli (720p)", "Yüksek (1080p)"}
            allowed_encoder = {"Otomatik (en hızlı)", "libx264 (uyumlu)", "NVIDIA NVENC", "Intel Quick Sync", "AMD AMF"}
            with STORE.lock:
                output = str(data.get("output_dir", STORE.settings.output_dir)).strip()
                if output:
                    output_path = Path(output).expanduser()
                    output_path.mkdir(parents=True, exist_ok=True)
                    STORE.settings.output_dir = str(output_path)
                quality = str(data.get("quality", STORE.settings.quality))
                encoder = str(data.get("encoder", STORE.settings.encoder))
                if quality in allowed_quality:
                    STORE.settings.quality = quality
                if encoder in allowed_encoder:
                    STORE.settings.encoder = encoder
                STORE.settings.save_chat = bool(data.get("save_chat", STORE.settings.save_chat))
                STORE.settings.headless_first = bool(data.get("headless_first", STORE.settings.headless_first))
                STORE.settings.auto_thumbnail = bool(data.get("auto_thumbnail", STORE.settings.auto_thumbnail))
                STORE.settings.auto_update = bool(data.get("auto_update", STORE.settings.auto_update))
                STORE.settings.segment_threads = max(1, min(int(data.get("segment_threads", STORE.settings.segment_threads) or 1), 8))
                STORE.settings.idle_shutdown_minutes = max(1, min(int(data.get("idle_shutdown_minutes", STORE.settings.idle_shutdown_minutes) or 3), 60))
                transcript_model = str(data.get("transcript_model", STORE.settings.transcript_model))
                if transcript_model in {"tiny", "base", "small"}:
                    STORE.settings.transcript_model = transcript_model
                STORE.save()
                result = asdict(STORE.settings)
            self._json({"settings": result})
            return True
        if method == "POST" and path == "/api/choose-folder":
            import tkinter as tk
            from tkinter import filedialog

            root = tk.Tk()
            root.withdraw()
            root.attributes("-topmost", True)
            chosen = filedialog.askdirectory(initialdir=STORE.settings.output_dir or str(Path.home()))
            root.destroy()
            self._json({"path": chosen or ""})
            return True
        if method == "POST" and path == "/api/open-output":
            output = Path(STORE.settings.output_dir).expanduser()
            output.mkdir(parents=True, exist_ok=True)
            open_path(output)
            self._json({"ok": True})
            return True
        if method == "POST" and path == "/api/open-logs":
            core.LOG_DIR.mkdir(parents=True, exist_ok=True)
            open_path(core.LOG_DIR)
            self._json({"ok": True})
            return True
        if method == "POST" and path == "/api/update/apply":
            if WORKER.busy:
                raise RuntimeError("Aktif işlem bitmeden güncelleme yapılamaz.")
            status = updater.check_update()
            if status.get("error"):
                self._json({"ok": False, "applied": False, "error": status["error"]}, 503)
                return True
            if not status.get("available"):
                self._json({"ok": True, "applied": False, "message": "EchoWraith zaten güncel."})
                return True
            outcome = updater.apply_update(status.get("latest", ""))
            if outcome.get("ok"):
                core.EventSink(BROKER).log(
                    "Güncelleme uygulandı; EchoWraith yeni sürümle yeniden başlatılıyor.",
                    "success",
                    stage="UPDATE",
                    code="UPDATE_APPLIED",
                )
                self._json({"ok": True, "applied": True, "message": "Güncelleme uygulandı. EchoWraith yeniden başlatılıyor."})
                threading.Thread(target=lambda: restart_server(delay=1.2), daemon=True, name="echowraith-update-restart").start()
            else:
                self._json({"ok": False, "applied": False, "error": outcome.get("error", "Bilinmeyen güncelleme hatası.")}, 409)
            return True
        if method == "POST" and path == "/api/leaving":
            global CLIENT_LEFT_AT
            CLIENT_LEFT_AT = time.monotonic()
            self._json({"ok": True})
            return True
        if method == "POST" and path == "/api/shutdown":
            self._json({"ok": True, "message": "EchoWraith kapatılıyor."})
            if SERVER_INSTANCE is not None:
                def stop_everything() -> None:
                    WORKER.shutdown(timeout=12.0)
                    if SERVER_INSTANCE is not None:
                        SERVER_INSTANCE.shutdown()

                threading.Thread(target=stop_everything, daemon=True, name="echowraith-shutdown").start()
            return True

        progress_match = re.fullmatch(r"/api/lessons/([^/]+)/progress", path)
        if method == "PATCH" and progress_match:
            with STORE.lock:
                lesson = lesson_or_error(unquote(progress_match.group(1)))
                lesson.last_position = max(0.0, float(data.get("position", lesson.last_position) or 0))
                lesson.duration = max(0.0, float(data.get("duration", lesson.duration) or 0))
                lesson.completed = bool(data.get("completed", lesson.completed))
                lesson.last_watched_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
                STORE.save()
            self._json({"ok": True})
            return True

        bookmark_match = re.fullmatch(r"/api/lessons/([^/]+)/bookmarks", path)
        if method == "POST" and bookmark_match:
            bookmark = {
                "id": str(data.get("id") or uuid.uuid4().hex),
                "time": max(0.0, float(data.get("time", 0) or 0)),
                "text": str(data.get("text", "")).strip()[:300],
            }
            if not bookmark["text"]:
                raise ValueError("Not boş olamaz.")
            with STORE.lock:
                lesson = lesson_or_error(unquote(bookmark_match.group(1)))
                lesson.bookmarks = [*lesson.bookmarks, bookmark]
                STORE.save()
            self._json({"bookmark": bookmark}, 201)
            return True

        delete_match = re.fullmatch(r"/api/lessons/([^/]+)/bookmarks/([^/]+)", path)
        if method == "DELETE" and delete_match:
            with STORE.lock:
                lesson = lesson_or_error(unquote(delete_match.group(1)))
                bookmark_id = unquote(delete_match.group(2))
                lesson.bookmarks = [item for item in lesson.bookmarks if str(item.get("id")) != bookmark_id]
                STORE.save()
            self._json({"ok": True})
            return True

        open_match = re.fullmatch(r"/api/lessons/([^/]+)/open", path)
        if method == "POST" and open_match:
            lesson = lesson_or_error(unquote(open_match.group(1)))
            output = Path(lesson.output_path).expanduser()
            if not output.is_file():
                raise FileNotFoundError("Video dosyası bulunamadı.")
            open_path(output)
            self._json({"ok": True})
            return True
        return False

    def _dispatch(self, method: str, head_only: bool = False) -> None:
        parsed = urlsplit(self.path)
        path = unquote(parsed.path)
        try:
            host = (self.headers.get("Host") or "").split(":", 1)[0].strip("[]").casefold()
            if host not in {HOST, "localhost"}:
                self._json({"error": "Yalnız yerel panel istekleri kabul edilir."}, 403, head_only)
                return
            origin = self.headers.get("Origin", "")
            if method in {"POST", "PATCH", "DELETE"} and origin:
                origin_host = (urlsplit(origin).hostname or "").casefold()
                if origin_host not in {HOST, "localhost"}:
                    self._json({"error": "Geçersiz yerel istek kaynağı."}, 403, head_only)
                    return
            if method in {"GET", "HEAD"} and self._api_get(path, parsed.query, head_only):
                return
            if method in {"POST", "PATCH", "DELETE"} and self._api_mutation(method, path):
                return
            if method in {"GET", "HEAD"}:
                self._static(path, head_only)
                return
            self._json({"error": "İstek yolu bulunamadı."}, 404, head_only)
        except KeyError as error:
            self._json({"error": str(error.args[0] if error.args else error)}, 404, head_only)
        except FileNotFoundError as error:
            self._json({"error": str(error)}, 404, head_only)
        except (ValueError, RuntimeError) as error:
            self._json({"error": str(error)}, 409 if isinstance(error, RuntimeError) else 400, head_only)
        except (BrokenPipeError, ConnectionResetError):
            return
        except Exception as error:
            core.EventSink(BROKER).exception("HTTP", error)
            self._json({"error": str(error)}, 500, head_only)

    def do_GET(self) -> None:  # noqa: N802
        self._dispatch("GET")

    def do_HEAD(self) -> None:  # noqa: N802
        self._dispatch("HEAD", head_only=True)

    def do_POST(self) -> None:  # noqa: N802
        self._dispatch("POST")

    def do_PATCH(self) -> None:  # noqa: N802
        self._dispatch("PATCH")

    def do_DELETE(self) -> None:  # noqa: N802
        self._dispatch("DELETE")


def find_port() -> int:
    for port in range(PREFERRED_PORT, PREFERRED_PORT + 40):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            try:
                sock.bind((HOST, port))
                return port
            except OSError:
                continue
    raise RuntimeError("Yerel panel için boş port bulunamadı.")


def focus_existing() -> bool:
    if not core.SERVER_FILE.exists():
        return False
    try:
        data = json.loads(core.SERVER_FILE.read_text(encoding="utf-8"))
        url = str(data.get("url", ""))
        response = requests.get(f"{url}/api/health", timeout=1.5)
        if response.ok:
            webbrowser.open(url)
            return True
    except (OSError, ValueError, requests.RequestException):
        pass
    return False


def restart_server(delay: float = 1.0) -> None:
    """Re-launch the app in place so freshly downloaded code takes effect.
    Guarded so the relaunched process never immediately auto-updates again."""
    time.sleep(max(0.0, delay))
    os.environ["ECHOWRAITH_UPDATED"] = "1"
    try:
        if SERVER_INSTANCE is not None:
            SERVER_INSTANCE.shutdown()
    except Exception:
        pass
    try:
        os.execv(sys.executable, [sys.executable, *sys.argv])
    except OSError:
        # Re-exec is best effort; if it fails the user can relaunch manually.
        os._exit(0)


def maybe_auto_update() -> None:
    """On launch, if enabled, bring local files up to date with GitHub before
    serving, then relaunch once. Any failure is non-fatal."""
    if os.getenv("ECHOWRAITH_UPDATED") == "1":
        return
    if not STORE.settings.auto_update:
        return
    try:
        result = updater.check_and_apply(timeout=8.0)
    except Exception as error:  # never block startup on an update problem
        core.DIAGNOSTICS.event("WARNING", "UPDATE", "Otomatik güncelleme denetimi yapılamadı.", code="UPDATE_SKIPPED", details=str(error))
        return
    if result.get("applied"):
        core.DIAGNOSTICS.event("INFO", "UPDATE", "Yeni sürüm indirildi; EchoWraith yeniden başlatılıyor.", code="UPDATE_APPLIED")
        os.environ["ECHOWRAITH_UPDATED"] = "1"
        try:
            os.execv(sys.executable, [sys.executable, *sys.argv])
        except OSError:
            pass


def notify_updates_available() -> None:
    """Background check that tells the open panel when an update is waiting
    (used when auto-update is off, or the check raced startup)."""
    try:
        status = updater.check_update(timeout=8.0)
    except Exception:
        return
    if status.get("available"):
        BROKER.put(("update_available", status))


def show_fatal_error(message: str) -> None:
    try:
        if os.name == "nt":
            import ctypes

            ctypes.windll.user32.MessageBoxW(0, message, core.APP_NAME, 0x10)
        else:
            print(message, file=sys.stderr)
    except Exception:
        print(message, file=sys.stderr)


def main() -> int:
    global SERVER_INSTANCE, LAST_CLIENT_SEEN
    if sys.version_info < (3, 10):
        raise RuntimeError("Python 3.10 veya daha yeni bir sürüm gerekli.")
    core.ensure_dirs()
    core.DIAGNOSTICS.event("INFO", "BOOT", "Başlangıç denetimleri çalıştırılıyor.", code="BOOT_CHECK")
    if focus_existing():
        return 0
    maybe_auto_update()
    if not WEB_ROOT.joinpath("index.html").is_file():
        raise RuntimeError("Web paneli dosyaları bulunamadı. Paketi yeniden çıkart.")
    try:
        probe = core.DATA_ROOT / ".write-test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
    except OSError as error:
        raise RuntimeError("EchoWraith veri klasörüne yazamıyor. Klasör izinlerini kontrol edin.") from error
    port = find_port()
    url = f"http://{HOST}:{port}"
    server = EchoWraithHTTPServer((HOST, port), EchoWraithHandler)
    SERVER_INSTANCE = server
    LAST_CLIENT_SEEN = time.monotonic()
    core.SERVER_FILE.write_text(
        json.dumps({"url": url, "pid": os.getpid(), "started_at": datetime.now(timezone.utc).isoformat()}),
        encoding="utf-8",
    )

    def cleanup() -> None:
        try:
            data = json.loads(core.SERVER_FILE.read_text(encoding="utf-8"))
            if int(data.get("pid", -1)) == os.getpid():
                core.SERVER_FILE.unlink(missing_ok=True)
        except (OSError, ValueError, json.JSONDecodeError):
            pass

    atexit.register(cleanup)

    def idle_watchdog() -> None:
        while SERVER_INSTANCE is server:
            time.sleep(5)
            now = time.monotonic()
            left_at = CLIENT_LEFT_AT
            explicit_close = left_at is not None and now - left_at > 15
            idle_limit = max(60, int(STORE.settings.idle_shutdown_minutes) * 60)
            idle_timeout = now - LAST_CLIENT_SEEN > idle_limit
            if WORKER.busy and not explicit_close:
                continue
            if explicit_close or idle_timeout:
                core.EventSink(BROKER).log(
                    "Panel kapatıldığı için gereksiz arka plan işlemleri sonlandırılıyor.",
                    "success",
                    stage="CLEANUP",
                    code="IDLE_SHUTDOWN",
                )
                # Closing the last panel is an explicit request to close the
                # application, including an active download/render. This also
                # kills the complete FFmpeg/Chromium child tree.
                WORKER.shutdown(timeout=12.0)
                server.shutdown()
                return

    threading.Thread(target=idle_watchdog, daemon=True, name="echowraith-idle-watchdog").start()
    threading.Thread(target=notify_updates_available, daemon=True, name="echowraith-update-notify").start()
    threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    core.EventSink(BROKER).log("Yerel panel hazır.", "success", stage="BOOT", code="PANEL_READY")
    try:
        server.serve_forever(poll_interval=0.25)
    finally:
        cleanup()
        server.server_close()
        SERVER_INSTANCE = None
        core.EventSink(BROKER).log("Tüm arka plan kaynakları kapatıldı.", "success", stage="CLEANUP", code="SHUTDOWN_DONE")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        core.ensure_dirs()
        core.DIAGNOSTICS.exception("FATAL", exc)
        show_fatal_error(str(exc))
        raise
