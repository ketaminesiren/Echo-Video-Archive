"""Self-update EchoWraith from GitHub.

GitHub is treated as the source of truth. On launch the app can check the
configured repository's latest commit and, if it differs from the one that was
last applied locally, download that revision and copy it over the local files.
Everything here is defensive: a failed or offline check never blocks startup,
and the previous install is backed up before anything is overwritten so a bad
update can be rolled back.
"""

from __future__ import annotations

import io
import json
import os
import shutil
import tarfile
import time
from pathlib import Path
from typing import Any, Optional

import requests

import echowraith_core as core


API_BASE = "https://api.github.com"
# Entries inside the single user-facing EchoWraith folder that may be replaced.
# User data lives outside the install directory (LOCALAPPDATA), so it is never
# touched. The root launcher is handled separately because it sits one level up.
PACKAGE_DIRNAME = "EchoWraith"
LAUNCHER_NAME = "BAŞLAT.bat"
UPDATABLE_ENTRIES = ("_app", "README.md")
_SKIP_DIRS = {"__pycache__", ".git"}


def _headers() -> dict[str, str]:
    headers = {"Accept": "application/vnd.github+json", "User-Agent": f"EchoWraith/{core.APP_VERSION}"}
    token = os.getenv("ECHOWRAITH_UPDATE_TOKEN", "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def local_revision() -> str:
    try:
        data = json.loads(core.REVISION_FILE.read_text(encoding="utf-8"))
        return str(data.get("sha", ""))
    except (OSError, ValueError):
        return ""


def _store_revision(sha: str) -> None:
    try:
        core.REVISION_FILE.parent.mkdir(parents=True, exist_ok=True)
        core.REVISION_FILE.write_text(
            json.dumps({"sha": sha, "applied_at": time.time(), "version": core.APP_VERSION}),
            encoding="utf-8",
        )
    except OSError:
        pass


def remote_revision(timeout: float = 8.0) -> dict[str, Any]:
    """Return {sha, message, date} for the tip of the configured branch."""
    url = f"{API_BASE}/repos/{core.UPDATE_REPO}/commits/{core.UPDATE_BRANCH}"
    response = requests.get(url, headers=_headers(), timeout=timeout)
    response.raise_for_status()
    payload = response.json()
    commit = payload.get("commit", {}) if isinstance(payload, dict) else {}
    return {
        "sha": str(payload.get("sha", "")),
        "message": str(commit.get("message", "")).splitlines()[0] if commit.get("message") else "",
        "date": str(commit.get("committer", {}).get("date", "")),
    }


def check_update(timeout: float = 8.0) -> dict[str, Any]:
    """Compare the local revision with GitHub. Never raises for the caller."""
    result: dict[str, Any] = {
        "available": False,
        "current": local_revision(),
        "latest": "",
        "message": "",
        "date": "",
        "error": "",
    }
    try:
        remote = remote_revision(timeout=timeout)
        result["latest"] = remote["sha"]
        result["message"] = remote["message"]
        result["date"] = remote["date"]
        current = result["current"]
        # A package may be weeks older yet have no revision marker. Treat its
        # first launch as an update so GitHub really is the source of truth;
        # after the successful apply the marker prevents repeat downloads.
        if not current:
            result["available"] = bool(remote["sha"])
        elif remote["sha"] and remote["sha"] != current:
            result["available"] = True
    except (requests.RequestException, ValueError, KeyError) as error:
        message = str(error)
        if "404" in message:
            message = (
                "Güncelleme deposuna erişilemedi (GitHub 404). Depo özelse "
                "ECHOWRAITH_UPDATE_TOKEN gerekir; son kullanıcı güncellemesi "
                "için depo veya ayrı güncelleme deposu herkese açık olmalıdır."
            )
        result["error"] = message
    return result


def _download_tarball(sha: str, timeout: float = 60.0) -> bytes:
    url = f"{API_BASE}/repos/{core.UPDATE_REPO}/tarball/{sha or core.UPDATE_BRANCH}"
    response = requests.get(url, headers=_headers(), timeout=timeout, stream=True)
    response.raise_for_status()
    buffer = io.BytesIO()
    for chunk in response.iter_content(chunk_size=1024 * 256):
        if chunk:
            buffer.write(chunk)
    return buffer.getvalue()


def _safe_extract(archive: tarfile.TarFile, destination: Path) -> Path:
    """Extract the archive under destination, rejecting path traversal, and
    return the single top-level directory GitHub wraps everything in."""
    destination.mkdir(parents=True, exist_ok=True)
    root_name = ""
    dest_resolved = destination.resolve()
    for member in archive.getmembers():
        if member.issym() or member.islnk():
            raise RuntimeError("Güncelleme arşivinde bağlantı türünde güvenli olmayan bir öğe bulundu.")
        target = (destination / member.name).resolve()
        if not str(target).startswith(str(dest_resolved) + os.sep) and target != dest_resolved:
            raise RuntimeError("Güncelleme arşivinde güvenli olmayan bir yol bulundu.")
        top = member.name.split("/", 1)[0]
        if top:
            root_name = root_name or top
    archive.extractall(destination)
    return destination / root_name


def _copy_tree(source: Path, target: Path) -> None:
    if source.is_dir():
        target.mkdir(parents=True, exist_ok=True)
        for child in source.iterdir():
            if child.name in _SKIP_DIRS:
                continue
            _copy_tree(child, target / child.name)
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def _archive_install_root(extracted_root: Path) -> Path:
    """Locate the install payload while accepting pre-folder-layout archives."""
    packaged = extracted_root / PACKAGE_DIRNAME
    if (packaged / "_app").is_dir():
        return packaged
    if (extracted_root / "_app").is_dir():
        return extracted_root
    raise RuntimeError("İndirilen güncelleme paketi beklenen dosyaları içermiyor.")


def apply_update(sha: str = "") -> dict[str, Any]:
    """Download the target revision and copy it over the local install after
    backing the current files up. Returns {ok, sha, error, backup}."""
    install_root = core.INSTALL_ROOT
    staging = core.CACHE_DIR / "update"
    shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir(parents=True, exist_ok=True)
    try:
        blob = _download_tarball(sha)
        with tarfile.open(fileobj=io.BytesIO(blob), mode="r:gz") as archive:
            extracted_root = _safe_extract(archive, staging)

        archive_install_root = _archive_install_root(extracted_root)
        present = [name for name in UPDATABLE_ENTRIES if (archive_install_root / name).exists()]
        if "_app" not in present:
            raise RuntimeError("İndirilen güncelleme paketi beklenen dosyaları içermiyor.")

        backup = core.CACHE_DIR / f"backup-{int(time.time())}"
        backup.mkdir(parents=True, exist_ok=True)
        for name in present:
            current_path = install_root / name
            if current_path.exists():
                _copy_tree(current_path, backup / name)

        for name in present:
            _copy_tree(archive_install_root / name, install_root / name)

        launcher_source = extracted_root / LAUNCHER_NAME
        if launcher_source.is_file():
            # New packages keep BAŞLAT.bat beside the EchoWraith folder. Older
            # installations keep the app payload at their root, so update the
            # launcher there without moving or deleting their working files.
            launcher_target_root = install_root.parent if install_root.name.casefold() == PACKAGE_DIRNAME.casefold() else install_root
            launcher_target = launcher_target_root / LAUNCHER_NAME
            if launcher_target.exists():
                _copy_tree(launcher_target, backup / LAUNCHER_NAME)
            _copy_tree(launcher_source, launcher_target)

        _store_revision(sha or local_revision())
        return {"ok": True, "sha": sha, "backup": str(backup), "error": ""}
    except (requests.RequestException, tarfile.TarError, OSError, RuntimeError, ValueError) as error:
        return {"ok": False, "sha": sha, "backup": "", "error": str(error)}
    finally:
        shutil.rmtree(staging, ignore_errors=True)


def check_and_apply(timeout: float = 8.0) -> dict[str, Any]:
    status = check_update(timeout=timeout)
    if not status.get("available"):
        return {"applied": False, **status}
    outcome = apply_update(status.get("latest", ""))
    return {"applied": bool(outcome.get("ok")), "outcome": outcome, **status}
