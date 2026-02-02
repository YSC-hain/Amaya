import sqlite3
import os

if not os.path.exists('data/'):
    os.makedirs('data/', exist_ok=True)

conn = sqlite3.connect('data/amaya.db')

user_version = conn.execute("PRAGMA user_version").fetchone()[0]
if user_version == 0:
    with open('src/storage/sql/db_init_v1.sql', 'r', encoding='utf-8') as f:
        init_sql = f.read()
    conn.executescript(init_sql)
    conn.execute("PRAGMA user_version = 1;")
elif user_version == 1:
    with open('src/storage/sql/db_preconfig_v1.sql', 'r', encoding='utf-8') as f:
        init_sql = f.read()
    conn.executescript(init_sql)

conn.commit()

__all__ = ["conn"]
