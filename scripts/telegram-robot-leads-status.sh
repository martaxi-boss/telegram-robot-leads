#!/usr/bin/env bash
# Telegram Robot Leads: safe status only (no Telegram requests, no DB writes).
set -euo pipefail

script_dir="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
python_bin="${PYTHON:-python3}"
vault="${TELEGRAM_ROBOT_LEADS_VAULT:-/root/project-secrets/telegram-robot-leads}"
metrics_root="${TELEGRAM_ROBOT_LEADS_METRICS_ROOT:-/opt/telegram-leads-optin}"

printf '=== Telegram Robot Leads: protected vault (metadata only) ===\n'
"$python_bin" "$script_dir/lead_health.py" --root "$vault" --no-pm2
printf '=== Telegram Robot Leads: opt-in metrics (read-only) ===\n'
"$python_bin" "$script_dir/growth_tracker.py" --root "$metrics_root" --stats
printf '=== PM2 intentionally not queried; status is not Telegram connectivity proof ===\n'
