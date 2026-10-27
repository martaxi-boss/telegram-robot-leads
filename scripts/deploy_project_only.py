#!/usr/bin/env python3
"""Transactional code-only installer for Telegram Robot Leads on its VPS.

Does not create or restart PM2 processes, access other projects, overwrite
private sessions, delete backups, or modify state. It can only modify the
explicitly declared tracked runtime files under /opt/telegram-robot-leads.
A separately verified owner-scoped activation is required after staging.
"""

from __future__ import annotations

import argparse
import io
import json
import os
from pathlib import Path
import re
import stat
import tarfile
import tempfile
import time

ROOT = Path("/opt/telegram-robot-leads")
VAULT = Path("/root/project-secrets/telegram-robot-leads")
MARKER = ".verified-source-commit"
BACKUP_NAME = ".telegram-leads-release-backups"
MAX_FILE_BYTES = 2 * 1024 * 1024

RUNTIME_FILES = (
    "scripts/lead_health.py",
    "scripts/leads_operational_report.py",
    "scripts/operation_policy.py",
    "scripts/organic_growth.py",
    "scripts/project_hygiene.py",
    "scripts/safe_runtime.py",
    "scripts/telegram-robot-leads-status.sh",
    "scripts/deploy_project_only.py",
)
SHA = re.compile(r"[0-9a-f]{40}\Z")


class InstallBlocked(RuntimeError):
    pass


def _directory(path: Path) -> None:
    if not path.is_absolute() or path.is_symlink():
        raise InstallBlocked("path_not_canonical")
    try:
        meta = path.lstat()
    except OSError as exc:
        raise InstallBlocked("project_directory_unavailable") from exc
    if not stat.S_ISDIR(meta.st_mode) or meta.st_uid != os.geteuid():
        raise InstallBlocked("project_directory_not_owned")


def _regular(path: Path, *, private: bool = False) -> os.stat_result:
    if path.is_symlink():
        raise InstallBlocked("project_file_symlink_refused")
    try:
        meta = path.lstat()
    except OSError as exc:
        raise InstallBlocked("project_file_unavailable") from exc
    if not stat.S_ISREG(meta.st_mode) or meta.st_uid != os.geteuid():
        raise InstallBlocked("project_file_not_owned")
    if private and stat.S_IMODE(meta.st_mode) & 0o077:
        raise InstallBlocked("private_file_permissions_invalid")
    return meta


def _validate_root_and_vault() -> None:
    if ROOT.resolve() != ROOT or VAULT.resolve() != VAULT:
        raise InstallBlocked("noncanonical_project_path")
    _directory(ROOT)
    _directory(ROOT / "scripts")
    _directory(VAULT)
    sessions = sorted(VAULT.glob("*.session"))
    if len(sessions) != 2:
        raise InstallBlocked("two_existing_sessions_required")
    for session in sessions:
        _regular(session, private=True)
    if not (ROOT / ".venv" / "bin" / "python").is_file():
        raise InstallBlocked("existing_python_venv_required")
    if not (ROOT / "main.py").is_file():
        raise InstallBlocked("existing_safe_entrypoint_required")


def _installed_sha() -> str:
    path = ROOT / MARKER
    _regular(path, private=True)
    current = path.read_text(encoding="ascii").strip()
    if not SHA.fullmatch(current):
        raise InstallBlocked("unrecognized_installed_source")
    return current


def _read_bundle(path: Path) -> dict[str, bytes]:
    if path.parent != ROOT or not path.name.startswith(".telegram-leads-"):
        raise InstallBlocked("bundle_path_not_project_scoped")
    info = _regular(path)
    if info.st_size > 8 * 1024 * 1024:
        raise InstallBlocked("bundle_too_large")
    payload: dict[str, bytes] = {}
    try:
        with tarfile.open(path, mode="r:gz") as tar:
            for member in tar:
                if (not member.isfile() or member.name not in RUNTIME_FILES
                        or member.name in payload
                        or member.size < 1 or member.size > MAX_FILE_BYTES):
                    raise InstallBlocked("bundle_unexpected_entry")
                stream = tar.extractfile(member)
                if stream is None:
                    raise InstallBlocked("bundle_unreadable")
                data = stream.read(MAX_FILE_BYTES + 1)
                if len(data) != member.size:
                    raise InstallBlocked("bundle_content_mismatch")
                payload[member.name] = data
    except (tarfile.TarError, OSError, EOFError) as exc:
        raise InstallBlocked("bundle_unreadable") from exc
    if set(payload) != set(RUNTIME_FILES):
        raise InstallBlocked("bundle_incomplete")
    for filename, data in payload.items():
        if filename.endswith(".py"):
            try:
                compile(data, filename, "exec")
            except (SyntaxError, ValueError, TypeError) as exc:
                raise InstallBlocked("bundle_python_syntax_invalid") from exc
    return payload


def _atomic_write(path: Path, data: bytes, *, mode: int = 0o600) -> None:
    fd, temp_path = tempfile.mkstemp(prefix=".telegram-leads-stage-", dir=path.parent)
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, "wb") as output:
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temp_path, path)
    finally:
        if os.path.lexists(temp_path):
            os.unlink(temp_path)


def install(
    bundle: Path, commit: str, expected: str, *, apply: bool = False
) -> dict:
    if not SHA.fullmatch(commit) or not SHA.fullmatch(expected):
        raise InstallBlocked("sha_invalid")
    _validate_root_and_vault()
    current = _installed_sha()
    if current == commit:
        return {"status": "ALREADY_INSTALLED", "installed_sha": current}
    if current != expected:
        raise InstallBlocked("installed_sha_mismatch_abort")
    payload = _read_bundle(bundle)
    original: dict[str, bytes | None] = {}
    original_mode: dict[str, int] = {}
    for rel in RUNTIME_FILES:
        path = ROOT / rel
        _directory(path.parent)
        if path.exists() or path.is_symlink():
            meta = _regular(path)
            if meta.st_size > MAX_FILE_BYTES:
                raise InstallBlocked("existing_file_oversized")
            original[rel] = path.read_bytes()
            original_mode[rel] = stat.S_IMODE(meta.st_mode)
        else:
            original[rel] = None
            original_mode[rel] = 0o644 if rel.endswith(".py") else 0o755
    if not apply:
        return {
            "status": "DRY_RUN", "previous_sha": current,
            "target_sha": commit, "runtime_files": len(RUNTIME_FILES),
            "sessions_preserved": 2,
        }

    backup_root = ROOT / BACKUP_NAME
    if backup_root.exists() or backup_root.is_symlink():
        _directory(backup_root)
    else:
        backup_root.mkdir(mode=0o700)
    backup_dir = backup_root / ("from-" + current[:12] + "-to-" + commit[:12])
    if backup_dir.exists() or backup_dir.is_symlink():
        raise InstallBlocked("deployment_backup_already_exists")
    backup_dir.mkdir(mode=0o700)
    manifest = {
        "previous_sha": current, "target_sha": commit,
        "paths": {rel: original[rel] is not None for rel in RUNTIME_FILES},
    }
    _atomic_write(
        backup_dir / "manifest.json",
        json.dumps(manifest, sort_keys=True).encode("utf-8"),
    )
    for rel, old_content in original.items():
        if old_content is None:
            continue
        destination = backup_dir / rel
        destination.parent.mkdir(parents=True, exist_ok=True)
        _atomic_write(destination, old_content)

    applied: list[str] = []
    try:
        for rel, new_content in payload.items():
            target = ROOT / rel
            if target.is_symlink():
                raise InstallBlocked("target_changed_during_install")
            _directory(target.parent)
            _atomic_write(target, new_content, mode=original_mode[rel])
            applied.append(rel)
        _atomic_write(ROOT / MARKER, (commit + "\n").encode("ascii"))
    except BaseException:
        # Roll back only the same named project files. Preserve the full backup
        # for forensic review and do not touch private sessions or other apps.
        for rel in reversed(applied):
            destination = ROOT / rel
            if original[rel] is None:
                if destination.is_file() and not destination.is_symlink():
                    destination.unlink()
            else:
                _atomic_write(
                    destination, original[rel], mode=original_mode[rel]
                )
        _atomic_write(ROOT / MARKER, (current + "\n").encode("ascii"))
        raise

    return {
        "status": "STAGED_NOT_ACTIVATED",
        "previous_sha": current,
        "installed_sha": _installed_sha(),
        "runtime_files": len(applied),
        "sessions_preserved": 2,
        "backup_directory": BACKUP_NAME + "/" + backup_dir.name,
        "other_projects_modified": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--expected-installed", required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm-telegram-only", action="store_true")
    args = parser.parse_args()
    if args.apply and not args.confirm_telegram_only:
        parser.error("installation requires --confirm-telegram-only")
    try:
        result = install(
            args.bundle, args.commit, args.expected_installed, apply=args.apply
        )
        print(json.dumps(result, sort_keys=True))
        return 0
    except (InstallBlocked, OSError, ValueError) as exc:
        reason = str(exc) if isinstance(exc, InstallBlocked) else "local_io_error"
        print(json.dumps({"status": "BLOCKED", "reason": reason},
                         sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
