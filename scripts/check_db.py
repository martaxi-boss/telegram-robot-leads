import sqlite3
import os

db_path = "/root/TELEGRAM-IPTVPN/users.db"
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT status, COUNT(*) FROM users GROUP BY status;")
    rows = cursor.fetchall()
    print("Status counts:")
    for row in rows:
        print(f"{row[0]}: {row[1]}")
    
    cursor.execute("SELECT region, COUNT(*) FROM users WHERE status='pending' GROUP BY region;")
    rows = cursor.fetchall()
    print("\nPending by region:")
    for row in rows:
        print(f"{row[0]}: {row[1]}")
    conn.close()
else:
    print("DB not found")
