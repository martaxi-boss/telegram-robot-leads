#!/usr/bin/env python3
"""Resumo dos registos em SQLite (adder_daily + últimos eventos). Executar na VPS: python3 ver_metricas.py"""
import sqlite3
import sys
from pathlib import Path

DB = Path(__file__).resolve().parent / "users.db"
DAYS = int(sys.argv[1]) if len(sys.argv) > 1 else 7


def main():
    if not DB.exists():
        print(f"Não encontrei {DB}")
        sys.exit(1)
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='adder_daily'")
    if not cur.fetchone():
        print("(tabelas adder_* ainda não existem — corre o bot uma vez ou: venv/bin/python3 -c \"import asyncio; from main import init_db; asyncio.run(init_db())\")")
        conn.close()
        return

    print(f"=== Resumo diário (últimos {DAYS} dias) ===\n")
    cur.execute(
        """
        SELECT * FROM adder_daily
        ORDER BY day DESC, session
        LIMIT ?
        """,
        (DAYS * 4,),
    )
    rows = cur.fetchall()
    if not rows:
        print("(ainda sem linhas em adder_daily — o bot precisa de correr após a atualização)\n")
    else:
        for r in rows:
            print(
                f"{r['day']} | {r['session']}: meta {r['target_adds']} | OK {r['adds_ok']} | "
                f"priv {r['err_privacy']} | mutual {r['err_not_mutual']} | "
                f"flood {r['err_floodwait']} | rate {r['err_rate_limit']} | outro {r['err_other']} | "
                f"fila_vazia×{r['queue_empty_events']} | scrape+{r['scrape_new_users']} ({r['scrape_runs']} rondas) | "
                f"almoço×{r['lunch_breaks']} | meta_ok={r['target_met']}"
            )
        print()

    print("=== Últimos 25 eventos ===\n")
    cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='adder_events'"
    )
    if not cur.fetchone():
        print("(sem adder_events)")
    else:
        cur.execute(
            """
            SELECT ts, day, session, event_type, detail, username
            FROM adder_events
            ORDER BY id DESC
            LIMIT 25
            """
        )
        for r in cur.fetchall():
            who = f" @{r['username']}" if r["username"] else ""
            print(f"{r['ts']} | {r['session']} | {r['event_type']}{who} | {r['detail'] or ''}")

    conn.close()


if __name__ == "__main__":
    main()
