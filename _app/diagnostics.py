from __future__ import annotations

import json
import logging
import os
import platform
import re
import shutil
import sys
import threading
import traceback
import uuid
import zipfile
from dataclasses import asdict, is_dataclass
from datetime import datetime, timedelta, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


SECRET_KEYS = {
    "authorization",
    "cookie",
    "cookies",
    "password",
    "passwd",
    "secret",
    "sifre",
    "şifre",
    "token",
    "csrf",
    "source_url",
    "href",
}

URL_SECRET_KEYS = SECRET_KEYS | {
    "auth",
    "code",
    "credential",
    "expires",
    "key",
    "meetingid",
    "passcode",
    "policy",
    "pwd",
    "signature",
    "sig",
}


def _safe_url(value: str) -> str:
    try:
        parsed = urlsplit(value)
        if not parsed.scheme or not parsed.netloc:
            return value
        filtered = []
        for key, item in parse_qsl(parsed.query, keep_blank_values=True):
            lowered = key.casefold()
            hide = lowered in URL_SECRET_KEYS or any(token in lowered for token in ("token", "secret", "auth", "sign", "pass"))
            filtered.append((key, "[GİZLENDİ]" if hide else item))
        safe_path = re.sub(r"(?<=/)[A-Za-z0-9_-]{28,}(?=/|$)", "[KAYIT-ID-GİZLENDİ]", parsed.path)
        return urlunsplit((parsed.scheme, parsed.netloc, safe_path, urlencode(filtered), ""))
    except Exception:
        return value


def redact_text(value: Any) -> str:
    text = str(value or "")
    text = re.sub(r"(?i)\b(cookie|set-cookie|authorization)\s*:\s*[^\r\n]+", r"\1: [GİZLENDİ]", text)
    text = re.sub(r"(?i)(password|passwd|sifre|şifre|token|authorization|cookie|csrf)\s*[:=]\s*[^\s,;]+", r"\1=[GİZLENDİ]", text)
    text = re.sub(r"(?i)bearer\s+[A-Za-z0-9._~+\-/]+=*", "Bearer [GİZLENDİ]", text)
    text = re.sub(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", "[E-POSTA GİZLENDİ]", text, flags=re.I)
    text = re.sub(r"(?<!\d)(?:\+?90\s*)?0?5\d{2}[\s.-]*\d{3}[\s.-]*\d{2}[\s.-]*\d{2}(?!\d)", "[TELEFON GİZLENDİ]", text)
    return re.sub(r"https?://[^\s\]\[()<>]+", lambda match: _safe_url(match.group(0)), text)


def sanitize(value: Any, depth: int = 0) -> Any:
    if depth > 7:
        return "[DERİNLİK SINIRI]"
    if is_dataclass(value):
        value = asdict(value)
    if isinstance(value, dict):
        cleaned: dict[str, Any] = {}
        for key, item in value.items():
            name = str(key)
            if name.casefold() in SECRET_KEYS or any(token in name.casefold() for token in ("password", "sifre", "şifre", "token", "cookie")):
                cleaned[name] = "[GİZLENDİ]"
            else:
                cleaned[name] = sanitize(item, depth + 1)
        return cleaned
    if isinstance(value, (list, tuple, set)):
        return [sanitize(item, depth + 1) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return redact_text(value)


def diagnose_exception(error: BaseException) -> dict[str, Any]:
    raw = f"{type(error).__name__}: {error}"
    lower = raw.casefold()
    result = {
        "code": "UNEXPECTED",
        "reason": "Beklenmeyen bir işlem hatası oluştu.",
        "suggestion": "Luna ayrıntıları kaydetti; otomatik tekrar denenecek.",
        "recoverable": True,
    }
    rules = (
        (("timeout", "timed out", "zaman aş"), "NETWORK_TIMEOUT", "Sunucu beklenen sürede yanıt vermedi.", "Bağlantı kısa bir beklemeden sonra yeniden denenecek."),
        (("connection", "dns", "name resolution", "network", "proxy"), "NETWORK", "İnternet veya sunucu bağlantısı kesildi.", "Bağlantı denetlenecek ve yarım indirme kaldığı yerden sürdürülecek."),
        (("401", "403", "unauthorized", "forbidden", "giriş", "login"), "AUTH", "Öğrenci oturumu geçersizleşmiş veya kayıt erişimi reddedilmiş.", "Kayıtlı oturum yenilenecek; gerekirse görünür giriş penceresi açılacak."),
        (("no space", "disk full", "yeterli boş", "errno 28"), "DISK_FULL", "Hedef diskte yeterli boş alan yok.", "Başka klasör seçin veya diskte yer açın."),
        (("permission", "access is denied", "errno 13"), "PERMISSION", "Dosya veya klasör yazma izni reddedildi.", "Kayıt klasörü değiştirilecek ya da uygulama normal kullanıcı hesabıyla yeniden açılacak."),
        (("ffmpeg", "ffprobe", "encoder", "codec"), "MEDIA_TOOL", "Video dönüştürme aracı bu kaydı işleyemedi.", "Uyumlu yazılım kodlayıcısı ve güvenli yeniden paketleme yöntemi denenecek."),
        (("chromium", "chrome", "playwright", "browser"), "BROWSER", "Arka plan tarayıcısı başlatılamadı veya sayfayı okuyamadı.", "Paketlenmiş tarayıcı, yeni profil ve son olarak görünür mod sırayla denenecek."),
        (("ders tablosu", "medya kaynağı", "site görünümü", "selector", "locator"), "SITE_LAYOUT", "Eğitim sitesinin sayfa yapısı beklenenden farklı görünüyor.", "Ağ istekleri, iframe'ler, indirme bağlantıları ve oynatıcı verileri alternatif yöntemlerle taranacak."),
        (("invalid data", "corrupt", "bozuk", "duration", "süre"), "MEDIA_CORRUPT", "İndirilen video eksik veya doğrulanamadı.", "Yarım dosya korunacak; yeniden indirme ve onarım sırasıyla denenecek."),
    )
    for needles, code, reason, suggestion in rules:
        if any(token in lower for token in needles):
            result.update(code=code, reason=reason, suggestion=suggestion)
            break
    if result["code"] in {"DISK_FULL", "PERMISSION"}:
        result["recoverable"] = False
    return result


class JsonLineHandler(logging.Handler):
    def __init__(self, path: Path, lock: threading.RLock):
        super().__init__()
        self.path = path
        self.lock = lock

    def emit(self, record: logging.LogRecord) -> None:
        payload = getattr(record, "payload", {"message": record.getMessage()})
        line = json.dumps(sanitize(payload), ensure_ascii=False, separators=(",", ":"))
        try:
            with self.lock:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                with self.path.open("a", encoding="utf-8") as handle:
                    handle.write(line + "\n")
        except OSError:
            pass


class StructuredLogger:
    def __init__(self, root: Path, app_name: str, version: str):
        self.root = root
        self.app_name = app_name
        self.version = version
        self.session_id = uuid.uuid4().hex[:12]
        self.lock = threading.RLock()
        self.root.mkdir(parents=True, exist_ok=True)
        self.text_path = self.root / "echowraith.log"
        self.json_path = self.root / "events.jsonl"
        self.logger = logging.getLogger(f"echowraith.{id(self)}")
        self.logger.setLevel(logging.DEBUG)
        self.logger.propagate = False
        text_handler = RotatingFileHandler(self.text_path, maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8")
        text_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%Y-%m-%d %H:%M:%S"))
        self.logger.addHandler(text_handler)
        self.logger.addHandler(JsonLineHandler(self.json_path, self.lock))
        self.event("INFO", "BOOT", f"{app_name} {version} günlük sistemi başlatıldı.", code="SESSION_START")

    def event(
        self,
        level: str,
        stage: str,
        message: str,
        *,
        code: str = "",
        details: Any = None,
        suggestion: str = "",
        lesson_key: str = "",
        attempt: int = 0,
    ) -> dict[str, Any]:
        clean_message = redact_text(message)
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "session_id": self.session_id,
            "level": level.upper(),
            "stage": stage.upper(),
            "code": code,
            "message": clean_message,
            "details": sanitize(details),
            "suggestion": redact_text(suggestion),
            "lesson_key": lesson_key,
            "attempt": attempt,
        }
        numeric = getattr(logging, level.upper(), logging.INFO)
        self.logger.log(numeric, f"[{payload['stage']}] {clean_message}" + (f" | {payload['code']}" if code else ""), extra={"payload": payload})
        return payload

    def exception(self, stage: str, error: BaseException, *, lesson_key: str = "", attempt: int = 0) -> dict[str, Any]:
        diagnosis = diagnose_exception(error)
        return self.event(
            "ERROR",
            stage,
            diagnosis["reason"],
            code=diagnosis["code"],
            details={"error": f"{type(error).__name__}: {error}", "traceback": traceback.format_exc(limit=12)},
            suggestion=diagnosis["suggestion"],
            lesson_key=lesson_key,
            attempt=attempt,
        )

    def recent(self, limit: int = 250) -> list[dict[str, Any]]:
        if not self.json_path.is_file():
            return []
        try:
            lines = self.json_path.read_text(encoding="utf-8", errors="replace").splitlines()[-max(1, min(limit, 2000)) :]
            return [json.loads(line) for line in lines if line.strip()]
        except (OSError, json.JSONDecodeError):
            return []

    def cleanup(self, days: int = 21) -> None:
        cutoff = datetime.now().timestamp() - timedelta(days=max(1, days)).total_seconds()
        for path in self.root.glob("*"):
            try:
                if path.is_file() and path.stat().st_mtime < cutoff and path.name not in {self.text_path.name, self.json_path.name}:
                    path.unlink()
            except OSError:
                continue

    def make_bundle(self, destination: Path, state_summary: Any, extra: dict[str, Any] | None = None) -> Path:
        destination.parent.mkdir(parents=True, exist_ok=True)
        system = {
            "app": self.app_name,
            "version": self.version,
            "session_id": self.session_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "python": sys.version,
            "executable": sys.executable,
            "platform": platform.platform(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "cpu_count": os.cpu_count(),
            "free_disk_bytes": shutil.disk_usage(self.root).free,
            "extra": sanitize(extra or {}),
        }
        with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(self.root.glob("*.log*")) + sorted(self.root.glob("*.jsonl*")):
                if path.is_file():
                    archive.write(path, f"logs/{path.name}")
            archive.writestr("system.json", json.dumps(system, ensure_ascii=False, indent=2))
            archive.writestr("state-summary.json", json.dumps(sanitize(state_summary), ensure_ascii=False, indent=2))
            archive.writestr(
                "OKU_BENI.txt",
                "Bu paket EchoWraith tanılama kayıtlarını içerir. Parola, oturum çerezi ve erişim bağlantıları otomatik olarak gizlenmiştir.\n",
            )
        return destination
