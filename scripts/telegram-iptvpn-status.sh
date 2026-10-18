#!/usr/bin/env bash
# Historical entrypoint kept for compatibility.
# TELEGRAM-IPTVPN was renamed Telegram Robot Leads; do NOT open a legacy DB
# or print Telegram account logs. Use the canonical read-only health script.
set -euo pipefail
script_dir="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
exec bash "$script_dir/telegram-robot-leads-status.sh" "$@"
