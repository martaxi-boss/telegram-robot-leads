#!/usr/bin/env bash
# Estado rápido do projecto TELEGRAM-IPTVPN (PM2 + fila + último log).
set -euo pipefail
echo "=== PM2 TELEGRAM-IPTVPN ==="
pm2 describe TELEGRAM-IPTVPN 2>/dev/null | grep -E 'status|uptime|restarts|exec cwd|script path' || true
echo
echo "=== users.db (contagens) ==="
/root/TELEGRAM-IPTVPN/.venv/bin/python3 << 'PY'
import sqlite3
p = "/root/TELEGRAM-IPTVPN/users.db"
con = sqlite3.connect(p)
c = con.cursor()
c.execute("SELECT status, COUNT(*) FROM users GROUP BY status ORDER BY 2 DESC")
for row in c.fetchall():
    print(f"  {row[0]}: {row[1]}")
c.execute(
    "SELECT day, session, adds_ok, scrape_new_users FROM adder_daily ORDER BY day DESC, session LIMIT 4"
)
print("  adder_daily (4 linhas):")
for row in c.fetchall():
    print(f"    {row}")
con.close()
PY
echo
echo "=== telethon_adder.log (últimas 6 linhas) ==="
tail -6 /root/TELEGRAM-IPTVPN/telethon_adder.log 2>/dev/null || echo "(sem log)"
