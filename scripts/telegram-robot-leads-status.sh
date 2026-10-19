#!/usr/bin/env bash
# Telegram Robot Leads: safe status only (no Telegram requests, no DB writes).
set -euo pipefail

script_dir="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
python_bin="${PYTHON:-python3}"
vault="${TELEGRAM_ROBOT_LEADS_VAULT:-/root/project-secrets/telegram-robot-leads}"
metrics_root="${TELEGRAM_ROBOT_LEADS_METRICS_ROOT:-/opt/telegram-leads-optin}"

printf '=== Telegram Robot Leads: protected vault (metadata only) ===\n'
"$python_bin" "$script_dir/lead_health.py" --root "$vault"
printf '=== Telegram Robot Leads: opt-in metrics (read-only) ===\n'
"$python_bin" "$script_dir/growth_tracker.py" --root "$metrics_root" --stats
printf '=== Robot Leads: evidence-based operational snapshot (redacted) ===\n'
runtime_python="/opt/telegram-robot-leads/.venv/bin/python"
if [[ -x "$runtime_python" ]]; then
  "$runtime_python" "$script_dir/leads_operational_report.py" \
    --vault "$vault" \
    --expected-source "${TELEGRAM_LEADS_EXPECTED_SOURCE:-c9ee64a2d5493e40a33cc6a6d6265c1452caa3da}"
else
  printf '=== Operational snapshot unavailable: runtime Python missing ===\n'
fi
printf '=== PM2 state is read-only and does not prove Telegram connectivity ===\n'
