#!/usr/bin/env python3
"""Offline growth intelligence for the existing Telegram Robot Leads project.

Ranks PUBLIC group metadata for permission-based cross-promotion and aggregates
observed campaign membership events. No Telegram calls, member enumeration,
unsolicited messages, account creation, automatic group joins, or mutations.
"""
from __future__ import annotations

import argparse
from contextlib import closing
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import re
import sqlite3
import stat
import sys
import unicodedata
from urllib.parse import quote

from public_group_discovery import DEFAULT_CATALOG, DiscoveryBlocked, read_catalog

DEFAULT_METRICS_DB = Path("/opt/telegram-leads-optin/growth_metrics.sqlite3")
TARGET_RE = re.compile(r"@[A-Za-z][A-Za-z0-9_]{4,31}\Z")
MAX_GROUP_RESULTS = 25
MAX_CAMPAIGN_RESULTS = 50

# Relevance is an EXPLANATION of matched public metadata, not a claim about
# member count, audience quality, audience consent, or contact permissions.
SIGNALS = (
    ("iptv", 43, ("iptv",)),
    ("portugal", 19, ("portugal", "portugues", "portuguese", "pt-pt")),
    ("streaming", 13, ("streaming",)),
    ("televisao", 13, ("televisao", "canais", "tv online")),
    ("entretenimento", 8, ("filmes", "series", "cinema")),
)
UNRELATED = ("casino", "apostas", "betting", "poker", "spam", "scam")


class RadarBlocked(RuntimeError):
    """A read-only source does not meet the operator's privacy constraints."""


def _ascii(value: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", value.casefold())
                   if not unicodedata.combining(c))


def _matched(text: str, terms: tuple[str, ...]) -> bool:
    return any(re.search(r"(?<![a-z0-9])" + re.escape(term) + r"(?![a-z0-9])",
                         text) is not None for term in terms)


def rank_public_groups(catalog: dict, target: str, *, now: datetime,
                       limit: int = 12) -> list[dict]:
    """Deterministic public-metadata ranking; does not inspect participants."""
    if not TARGET_RE.fullmatch(target) or not 1 <= limit <= MAX_GROUP_RESULTS:
        raise RadarBlocked("invalid_target_or_result_limit")
    if not isinstance(catalog, dict) or not isinstance(catalog.get("groups"), dict):
        raise RadarBlocked("catalog_invalid")
    selected: list[dict] = []
    for key, item in catalog["groups"].items():
        if not isinstance(item, dict):
            continue
        username = item.get("username")
        title = item.get("title")
        keywords = item.get("matched_keywords")
        if (not isinstance(username, str) or not TARGET_RE.fullmatch(username)
                or not isinstance(key, str) or key != username.casefold()
                or username.casefold() == target.casefold()
                or not isinstance(title, str) or len(title) > 120
                or not isinstance(keywords, list)
                or not all(isinstance(k, str) and len(k) <= 64 for k in keywords)):
            continue
        public_text = _ascii(" ".join([username, title] + keywords))
        if _matched(public_text, UNRELATED):
            continue
        reasons = [name for name, weight, terms in SIGNALS
                   if _matched(public_text, terms)]
        if not reasons:
            continue
        score = sum(weight for name, weight, terms in SIGNALS if name in reasons)
        seen = item.get("last_seen_at")
        try:
            observed_at = datetime.fromisoformat(seen)
            if observed_at.tzinfo is None:
                raise ValueError("naive date")
            if timedelta(0) <= now - observed_at.astimezone(timezone.utc) <= timedelta(days=30):
                score += 8
                reasons.append("observado_30d")
        except (TypeError, ValueError, OverflowError):
            pass
        if len(set(k.casefold() for k in keywords)) >= 2:
            score += 4
            reasons.append("multiplas_pesquisas")
        if score < 20:
            continue
        selected.append({
            "group": username,
            "title": "".join(c for c in title if c.isprintable())[:120],
            "public_url": "https://t.me/" + username[1:],
            "metadata_relevance_score": min(100, score),
            "signals": reasons,
            "members_estimate": None,
            "outreach": "REQUIRES_GROUP_ADMIN_PERMISSION",
        })
    selected.sort(key=lambda row: (-row["metadata_relevance_score"], row["group"].casefold()))
    return selected[:limit]


def _private_db(path: Path) -> None:
    if path.is_symlink() or path.parent.is_symlink():
        raise RadarBlocked("metrics_path_symlink")
    parent = path.parent.stat()
    info = path.stat()
    if (not stat.S_ISDIR(parent.st_mode) or parent.st_uid != os.geteuid()
            or not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid()
            or stat.S_IMODE(info.st_mode) & 0o077 or info.st_size > 128 * 1024 * 1024):
        raise RadarBlocked("metrics_permissions_or_size_invalid")


def campaign_snapshot(path: Path, *, now: datetime) -> dict:
    """Read an existing metrics SQLite DB in read-only mode; never create one."""
    if not path.exists() and not path.is_symlink():
        return {"status": "NOT_CONFIGURED", "observed_joins_7d": None,
                "observed_joins_30d": None, "campaigns": []}
    _private_db(path)
    uri = "file:" + quote(str(path.resolve()), safe="/") + "?mode=ro"
    try:
        with closing(sqlite3.connect(uri, uri=True, timeout=2)) as db:
            db.execute("PRAGMA query_only=ON")
            required = {"events", "campaigns"}
            names = {row[0] for row in db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name IN ('events','campaigns')")}
            if names != required:
                raise RadarBlocked("metrics_schema_unavailable")
            windows: dict[int, dict[str, dict[str, int]]] = {}
            for days in (7, 30):
                cutoff = (now - timedelta(days=days)).isoformat()
                by_source: dict[str, dict[str, int]] = {}
                query = """SELECT COALESCE(c.name, 'unattributed'),e.kind,COUNT(*)
                           FROM events e LEFT JOIN campaigns c ON c.id=e.campaign_id
                           WHERE e.occurred_at >= ?
                           GROUP BY COALESCE(c.name, 'unattributed'),e.kind"""
                for source, kind, count in db.execute(query, (cutoff,)):
                    if kind not in ("requested", "joined", "left"):
                        continue
                    label = source if isinstance(source, str) and source.isprintable() and len(source) <= 32 else "unattributed"
                    by_source.setdefault(label, {"requested": 0, "joined": 0, "left": 0})[kind] += count
                windows[days] = by_source
    except sqlite3.DatabaseError as exc:
        raise RadarBlocked("metrics_database_unreadable") from None

    names = set(windows[7]) | set(windows[30])
    rows = []
    for name in names:
        week = windows[7].get(name, {})
        month = windows[30].get(name, {})
        rows.append({
            "campaign": name,
            "requested_30d": month.get("requested", 0),
            "joined_7d": week.get("joined", 0),
            "joined_30d": month.get("joined", 0),
            "left_30d": month.get("left", 0),
        })
    rows.sort(key=lambda c: (-c["joined_30d"], -c["requested_30d"], c["campaign"].casefold()))
    return {
        "status": "OBSERVED_EVENTS",
        "observed_joins_7d": sum(v.get("joined", 0) for v in windows[7].values()),
        "observed_joins_30d": sum(v.get("joined", 0) for v in windows[30].values()),
        "campaigns": rows[:MAX_CAMPAIGN_RESULTS],
        "note": "Transitions observed by the existing metrics bot, not current membership or unique persons.",
    }


def build_radar(*, catalog_path: Path = DEFAULT_CATALOG,
                metrics_db: Path = DEFAULT_METRICS_DB,
                target: str = "@iptvpncode", limit: int = 12,
                now: datetime | None = None) -> dict:
    if not TARGET_RE.fullmatch(target) or not 1 <= limit <= MAX_GROUP_RESULTS:
        raise RadarBlocked("invalid_target_or_result_limit")
    reference = now or datetime.now(timezone.utc)
    if reference.tzinfo is None:
        raise RadarBlocked("naive_clock")
    if catalog_path.is_symlink() or catalog_path.parent.is_symlink():
        raise RadarBlocked("catalog_path_symlink")
    if catalog_path.exists():
        try:
            catalog = read_catalog(catalog_path)
        except (DiscoveryBlocked, OSError, ValueError) as exc:
            raise RadarBlocked("catalog_unreadable") from None
        groups = rank_public_groups(catalog, target, now=reference.astimezone(timezone.utc),
                                    limit=limit)
        discovered_count = len(catalog["groups"])
        catalog_status = "AVAILABLE"
    else:
        groups, discovered_count, catalog_status = [], 0, "NOT_CONFIGURED"
    metrics = campaign_snapshot(metrics_db, now=reference.astimezone(timezone.utc))
    next_steps = []
    if not groups:
        next_steps.append("EXPAND_PUBLIC_TOPIC_DISCOVERY")
    else:
        next_steps.append("REVIEW_PUBLIC_GROUPS_FOR_ADMIN_APPROVED_PARTNERSHIPS")
    if metrics["status"] != "OBSERVED_EVENTS":
        next_steps.append("ENABLE_OWN_GROUP_JOIN_EVENT_MEASUREMENT")
    elif not metrics["observed_joins_30d"]:
        next_steps.append("TEST_DISTRIBUTION_IN_OWN_OR_APPROVED_CHANNELS")
    else:
        next_steps.append("PRIORITIZE_SOURCES_WITH_MEASURED_JOINS")
    return {
        "status": "OFFLINE_GROWTH_RADAR",
        "read_only": True,
        "telegram_requests": 0,
        "messages_sent": 0,
        "users_enumerated": 0,
        "target": target,
        "catalog_status": catalog_status,
        "public_groups_discovered": discovered_count,
        "public_groups_ranked": groups,
        "campaign_measurement": metrics,
        "next_steps": next_steps,
        "note": "Scores reflect public metadata only; no claims of real users or guaranteed group growth.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--metrics-db", type=Path, default=DEFAULT_METRICS_DB)
    parser.add_argument("--target", default="@iptvpncode")
    parser.add_argument("--top", type=int, default=12)
    args = parser.parse_args()
    try:
        print(json.dumps(build_radar(catalog_path=args.catalog, metrics_db=args.metrics_db,
                                     target=args.target, limit=args.top),
                         ensure_ascii=False, sort_keys=True))
        return 0
    except (RadarBlocked, OSError) as exc:
        reason = str(exc) if isinstance(exc, RadarBlocked) else "project_source_unavailable"
        print(json.dumps({"status": "BLOCKED", "reason": reason},
                         sort_keys=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
