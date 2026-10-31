#!/usr/bin/env python3
"""Redacted, read-only operational report for this existing Telegram Robot Leads.

No Telegram calls, logins, writes, PM2 restarts, invitations or group changes.
The report distinguishes GitHub installation, offline session readiness,
PM2 process status, and *observed* public-discovery cycle evidence.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import stat
import sys
import time
from typing import Any

from lead_health import PROCESS_NAME, read_pm2
from organic_growth import preview as growth_preview
from member_groups import REGISTRY_PATH, RegistryBlocked, read_registry
from operation_policy import PolicyBlocked, load_state
from public_group_discovery import DEFAULT_CATALOG, DiscoveryBlocked, read_catalog, public_join_url
from safe_runtime import (
    DEFAULT_EVENT_JOURNAL,
    DEFAULT_STATE,
    load_approved_users,
    load_group_allowlist,
)
from telethon_sessions import DEFAULT_VAULT, ProbeBlocked, inspect

DEFAULT_CHECKOUT = Path("/opt/telegram-robot-leads")
IDENTIFIER = re.compile(r"[A-Za-z0-9_:-]{1,80}\Z")
SHA256 = re.compile(r"[0-9a-f]{40}\Z")
MAX_EVENT_TAIL_BYTES = 65536
RECENT_CYCLE_SECONDS = 1800


def _redacted_reason(reason: Any) -> str:
    """Allow bounded stable machine codes, never exception text with secrets."""
    return reason if isinstance(reason, str) and IDENTIFIER.fullmatch(reason) else "unavailable"


def _private_regular(path: Path, *, max_bytes: int | None = None) -> None:
    if path.is_symlink() or path.parent.is_symlink():
        raise ValueError("path_symlink_invalid")
    st = path.stat()
    if (not stat.S_ISREG(st.st_mode) or st.st_uid != os.geteuid()
            or stat.S_IMODE(st.st_mode) & 0o077):
        raise ValueError("file_permissions_invalid")
    if max_bytes is not None and st.st_size > max_bytes:
        raise ValueError("file_too_large")


def _private_directory(path: Path) -> None:
    if path.is_symlink():
        raise ValueError("directory_symlink_invalid")
    st = path.stat()
    if (not stat.S_ISDIR(st.st_mode) or st.st_uid != os.geteuid()
            or stat.S_IMODE(st.st_mode) & 0o077):
        raise ValueError("directory_permissions_invalid")


def _source(checkout: Path, expected_sha: str | None) -> dict[str, Any]:
    marker = checkout / ".verified-source-commit"
    result: dict[str, Any] = {"verified": False, "matches_expected": None}
    if not marker.exists():
        result["reason"] = "provenance_marker_missing"
        return result
    try:
        _private_regular(marker, max_bytes=80)
        value = marker.read_text(encoding="ascii").strip()
        if not SHA256.fullmatch(value):
            raise ValueError("invalid_sha_marker")
        result["verified"] = True
        result["source_sha"] = value
        result["installed_at_epoch"] = int(marker.stat().st_mtime)
        if expected_sha is not None:
            result["matches_expected"] = value == expected_sha
    except (OSError, ValueError, UnicodeError) as exc:
        result["reason"] = _redacted_reason(str(exc))
    return result


def _vault(vault: Path) -> dict[str, Any]:
    """Validate existing session files without modifying or displaying them."""
    try:
        config = inspect(vault)
        group = config["group"]
        try:
            join_url = public_join_url(group)
        except DiscoveryBlocked:
            join_url = None
        return {
            "status": "SESSION_FILES_READABLE_NOT_ONLINE_VERIFIED",
            "accounts": len(config["entries"]),
            "api_source": config["api_source"],
            "own_application_api_configured": config["api_source"] == "private_app_credentials",
            "public_join_url": join_url,
            "online_verified": False,
        }
    except (ProbeBlocked, PermissionError, OSError, ValueError, UnicodeError) as exc:
        # Avoid printing exceptions from potentially credential-bearing paths.
        return {"status": "BLOCKED", "reason": _redacted_reason(str(exc)),
                "online_verified": False}


def _action_queue(vault: Path) -> dict[str, Any]:
    """Read only operator-selected queue counts; never expose handles.

    Finding public groups is not the same as authorizing any member additions.
    """
    try:
        _private_directory(vault)
        users = load_approved_users(vault)
        groups = load_group_allowlist(vault)
        return {
            "status": "READABLE",
            "approved_username_entries": len(users),
            "allowlisted_group_entries": len(groups),
            "member_queue_status": (
                "EMPTY" if not users else "OPERATOR_ENTRIES_NOT_ONLINE_VERIFIED"
            ),
        }
    except (ProbeBlocked, OSError, ValueError, UnicodeError) as exc:
        return {"status": "BLOCKED", "reason": _redacted_reason(str(exc))}


def _organic_model(vault: Path, session_info: dict[str, Any]) -> dict[str, Any]:
    """Return a redacted offline readiness signal; never contact Telegram."""
    url = session_info.get("public_join_url")
    if not isinstance(url, str) or not url.startswith("https://t.me/"):
        return {"status": "TARGET_NOT_VERIFIED", "enabled": False}
    target = "@" + url.rsplit("/", 1)[-1]
    try:
        return growth_preview(vault, target)
    except (ProbeBlocked, OSError, ValueError, UnicodeError) as exc:
        return {"status": "BLOCKED", "reason": _redacted_reason(str(exc)),
                "enabled": False}


def _discovery(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"status": "NOT_RUN", "public_groups": 0, "last_attempt_day": None}
    try:
        _private_directory(path.parent)
        data = read_catalog(path)
        attempts = data.get("regional_attempts", {})
        if not isinstance(attempts, dict):
            raise DiscoveryBlocked("regional_attempts_invalid")
        counts = {"PT_ES": 0, "EU_OTHER": 0}
        for item in data["groups"].values():
            if not isinstance(item, dict):
                continue
            observed = item.get("matched_regions", [])
            if isinstance(observed, list):
                for region in counts:
                    if region in observed:
                        counts[region] += 1
        return {
            "status": "CATALOG_PRESENT",
            "public_groups": len(data["groups"]),
            "last_attempt_day": data.get("last_attempt_day"),
            "last_scan_at": data.get("last_scan_at"),
            "regional_attempts": {
                key: attempts.get(key) if isinstance(attempts.get(key), str)
                else None for key in ("1", "2")
            },
            "public_groups_by_search_region": counts,
            "regional_classification": "SEARCH_TERMS_NOT_VERIFIED_GEOGRAPHY",
        }
    except (DiscoveryBlocked, OSError, ValueError) as exc:
        return {"status": "BLOCKED", "reason": _redacted_reason(str(exc))}


def _memberships(path: Path) -> dict[str, Any]:
    """Aggregate verified membership evidence without exposing group identities."""
    if not path.exists():
        return {"status": "NOT_CREATED", "confirmed_total": 0}
    try:
        data = read_registry(path)
        accounts: dict[str, dict[str, Any]] = {}
        for number in ("1", "2"):
            account = data["accounts"][number]
            records = account["groups"].values()
            accounts[number] = {
                "confirmed": sum(item["status"] == "MEMBER_CONFIRMED"
                                 for item in records),
                "not_reconfirmed": sum(item["status"] == "NOT_RECONFIRMED"
                                       for item in records),
                "last_attempt_day": account["last_attempt_day"],
            }
        return {"status": "READABLE",
                "confirmed_total": sum(a["confirmed"] for a in accounts.values()),
                "accounts": accounts,
                "note": "OWN_DIALOGS_MATCHED_WITH_PUBLIC_DISCOVERY_ONLY"}
    except (RegistryBlocked, OSError, ValueError) as exc:
        return {"status": "BLOCKED", "reason": _redacted_reason(str(exc))}


def _operation_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"status": "NOT_CREATED", "accounts_blocked": None,
                "pending_member_actions": None}
    try:
        _private_directory(path.parent)
        _private_regular(path, max_bytes=8 * 1024 * 1024)
        state = load_state(path)
        return {
            "status": "READABLE",
            "accounts_blocked": sum(
                state["accounts"][str(i)]["blocked"] for i in (1, 2)),
            "pending_member_actions": len(state.get("pending_member_actions", {})),
            "pending_group_actions": len(state.get("pending_group_actions", {})),
            "member_additions_today_authorized": sum(
                state["accounts"][str(i)]["member_adds"] for i in (1, 2)),
            "join_request_approvals_today": sum(
                state["accounts"][str(i)].get("join_request_approvals", 0)
                for i in (1, 2)
            ),
            "pending_join_request_outcomes": len(
                state.get("pending_join_requests", {})
            ),
            "owner_notice_counts": {
                status: sum(isinstance(record, dict)
                            and record.get("owner_notice") == status
                            for record in state.get("approved_join_requests_done", {}).values())
                for status in ("ACCEPTED", "PENDING", "UNCERTAIN", "BLOCKED")
            },
            "owned_channel_promotion_records": len(
                state.get("owned_promotion", {})
            ),
        }
    except (PolicyBlocked, OSError, ValueError) as exc:
        return {"status": "BLOCKED", "reason": _redacted_reason(str(exc))}


def _events(path: Path, now: float) -> dict[str, Any]:
    if not path.exists():
        return {"status": "NO_EVENT_JOURNAL"}
    try:
        _private_directory(path.parent)
        _private_regular(path)
        with path.open("rb") as stream:
            stream.seek(0, os.SEEK_END)
            size = stream.tell()
            stream.seek(max(0, size - MAX_EVENT_TAIL_BYTES))
            tail = stream.read(MAX_EVENT_TAIL_BYTES)
        lines = tail.splitlines()
        if size > MAX_EVENT_TAIL_BYTES and lines:
            lines = lines[1:]  # Discard a possibly truncated line.
        for line in reversed(lines):
            try:
                event = json.loads(line)
            except (ValueError, UnicodeError):
                continue
            if not isinstance(event, dict) or not isinstance(event.get("event"), dict):
                continue
            kind = _redacted_reason(event["event"].get("kind"))
            timestamp = event.get("ts")
            if type(timestamp) not in (int, float) or not (0 <= timestamp <= now + 300):
                return {"status": "INVALID_TIMESTAMP"}
            age = max(0, int(now - timestamp))
            payload = event["event"]
            result: dict[str, Any] = {
                "status": "RECENT" if age <= RECENT_CYCLE_SECONDS else "STALE",
                "event_kind": kind,
                "age_seconds": age,
                "recorded_at_epoch": int(timestamp),
            }
            if kind == "cycle":
                discovery = payload.get("public_discovery")
                result["public_discovery_status"] = (
                    _redacted_reason(discovery.get("status"))
                    if isinstance(discovery, dict) else "NOT_REPORTED"
                )
                result["authorized_member_action_count"] = (
                    len(payload.get("member_actions", []))
                    if isinstance(payload.get("member_actions"), list) else None
                )
                result["blocked_action_count"] = (
                    len(payload.get("blocked", []))
                    if isinstance(payload.get("blocked"), list) else None
                )
                growth = payload.get("organic_growth")
                if isinstance(growth, dict):
                    owned = growth.get("owned_promotion")
                    intake = growth.get("join_requests")
                    result["owned_promotion_status"] = _redacted_reason(
                        owned.get("status") if isinstance(owned, dict) else None
                    )
                    result["join_request_status"] = _redacted_reason(
                        intake.get("status") if isinstance(intake, dict) else None
                    )
                    result["owned_posts_in_last_cycle"] = int(
                        isinstance(owned, dict)
                        and owned.get("status") == "POSTED"
                    )
                    result["approvals_in_last_cycle"] = int(
                        isinstance(intake, dict)
                        and intake.get("status") == "APPROVED_REQUEST"
                    )
                    notice = intake.get("owner_notice") if isinstance(intake, dict) else None
                    result["owner_notice_status"] = (
                        notice if notice in {"ACCEPTED", "UNCERTAIN", "BLOCKED"}
                        else "NOT_APPLICABLE"
                    )
            elif kind == "runtime_blocked":
                result["reason"] = _redacted_reason(payload.get("reason"))
            return result
        return {"status": "NO_VALID_EVENT"}
    except (OSError, ValueError) as exc:
        return {"status": "BLOCKED", "reason": _redacted_reason(str(exc))}


def _pm2(pm2_records: list[dict[str, Any]] | None) -> dict[str, Any]:
    if pm2_records is None:
        return {"status": "NOT_QUERIED"}
    matches = [p for p in pm2_records
               if isinstance(p, dict) and p.get("name") == PROCESS_NAME]
    if len(matches) != 1:
        return {"status": "WORKER_MISSING" if not matches else "DUPLICATE_WORKER"}
    environment = matches[0].get("pm2_env", {})
    if not isinstance(environment, dict):
        return {"status": "INVALID_PM2_DATA"}
    return {"status": "ONLINE" if environment.get("status") == "online" else "OFFLINE",
            "restart_count": environment.get("restart_time")
            if type(environment.get("restart_time")) is int else None}


def build_report(
    *,
    vault: Path = DEFAULT_VAULT,
    checkout: Path = DEFAULT_CHECKOUT,
    catalog_path: Path = DEFAULT_CATALOG,
    state_path: Path = DEFAULT_STATE,
    membership_path: Path = REGISTRY_PATH,
    events_path: Path = DEFAULT_EVENT_JOURNAL,
    pm2_records: list[dict[str, Any]] | None = None,
    expected_sha: str | None = None,
    now: float | None = None,
) -> dict[str, Any]:
    """Assemble an evidence report; never infer online health from offline checks."""
    current = time.time() if now is None else now
    source = _source(checkout, expected_sha)
    accounts = _vault(vault)
    action_queue = _action_queue(vault)
    growth_model = _organic_model(vault, accounts)
    catalog = _discovery(catalog_path)
    operation = _operation_state(state_path)
    memberships = _memberships(membership_path)
    event = _events(events_path, current)
    pm2 = _pm2(pm2_records)
    verified_live = (
        source.get("verified") is True
        and (expected_sha is None or source.get("matches_expected") is True)
        and accounts.get("status") == "SESSION_FILES_READABLE_NOT_ONLINE_VERIFIED"
        and pm2["status"] == "ONLINE"
        and event.get("status") == "RECENT"
        and event.get("event_kind") == "cycle"
        and event.get("public_discovery_status") == "PUBLIC_DISCOVERY_COMPLETE"
        and catalog.get("status") == "CATALOG_PRESENT"
        # No state file is normal when discovery ran but no groups/users were
        # authorized for side-effecting work; never certify corrupt state.
        and operation.get("status") in {"READABLE", "NOT_CREATED"}
        and event.get("recorded_at_epoch", -1) >= source.get("installed_at_epoch", float("inf"))
    )
    if verified_live:
        result = "LIVE_PUBLIC_DISCOVERY_OBSERVED"
    elif pm2["status"] == "ONLINE":
        result = "PM2_ONLINE_DISCOVERY_NOT_VERIFIED"
    elif pm2["status"] == "NOT_QUERIED":
        result = "OFFLINE_ONLY"
    else:
        result = "NOT_LIVE_VERIFIED"
    # These are diagnostic indicators, not a claim about lifetime membership
    # or a request to bypass missing configuration.
    readiness = []
    if source.get("matches_expected") is False:
        readiness.append("INSTALLED_SOURCE_DIFFERS_FROM_EXPECTED")
    if accounts.get("api_source") == "published_android_fallback":
        readiness.append("PRIVATE_APPLICATION_CREDENTIALS_NOT_CONFIGURED")
    if action_queue.get("member_queue_status") == "EMPTY":
        readiness.append("NO_APPROVED_USERS_IN_DIRECT_ADD_QUEUE")
    if growth_model.get("status") == "NOT_CONFIGURED":
        readiness.append("ORGANIC_GROWTH_MODEL_NOT_CONFIGURED")
    if pm2.get("status") != "ONLINE":
        readiness.append("PROJECT_PM2_NOT_VERIFIED")
    if event.get("event_kind") == "cycle" and event.get(
        "authorized_member_action_count"
    ) == 0:
        readiness.append("LAST_CYCLE_NO_DIRECT_MEMBER_ACTIONS")

    return {
        "project": "telegram-robot-leads",
        "read_only": True,
        "telegram_requests": 0,
        "messages_sent": 0,
        "members_added": 0,
        "checked_at": datetime.fromtimestamp(current, timezone.utc).isoformat(),
        "status": result,
        "source": source,
        "sessions": accounts,
        "action_queue": action_queue,
        "organic_growth_model": growth_model,
        "readiness_indicators": readiness,
        "pm2": pm2,
        "public_discovery": catalog,
        "group_memberships": memberships,
        "operation_state": operation,
        "supervisor": event,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vault", type=Path, default=DEFAULT_VAULT)
    parser.add_argument("--checkout", type=Path, default=DEFAULT_CHECKOUT)
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--state", type=Path, default=DEFAULT_STATE)
    parser.add_argument("--memberships", type=Path, default=REGISTRY_PATH)
    parser.add_argument("--events", type=Path, default=DEFAULT_EVENT_JOURNAL)
    parser.add_argument("--expected-source", type=str)
    parser.add_argument("--with-pm2", action="store_true",
                        help="Opt in to PM2 query (may start a daemon for this user)")
    parser.add_argument("--no-pm2", action="store_true",
                        help="Compatibility option; no PM2 query is the default")
    args = parser.parse_args()
    if args.with_pm2 and args.no_pm2:
        parser.error("--with-pm2 and --no-pm2 are mutually exclusive")
    if args.expected_source and not SHA256.fullmatch(args.expected_source):
        parser.error("expected source must be a full 40-character Git SHA")
    records = None
    pm2_error = None
    if args.with_pm2:
        records, pm2_error = read_pm2()
    report = build_report(
        vault=args.vault, checkout=args.checkout, catalog_path=args.catalog,
        state_path=args.state, membership_path=args.memberships,
        events_path=args.events,
        pm2_records=records, expected_sha=args.expected_source,
    )
    if pm2_error:
        report["pm2"]["diagnostic"] = _redacted_reason(pm2_error)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
