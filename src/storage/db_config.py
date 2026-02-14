import aiosqlite
import os

conn: aiosqlite.Connection | None = None

async def init_db(db_path: str) -> None:
    db_dir = os.path.dirname(db_path)
    if not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)
    global conn
    conn = await aiosqlite.connect(db_path)

    async with conn.execute("PRAGMA user_version") as cursor:
        row = await cursor.fetchone()
        user_version = row[0]

        if user_version == 0:
            with open('src/storage/sql/db_init_v1.sql', 'r', encoding='utf-8') as f:
                init_sql = f.read()
                await conn.executescript(init_sql)
            await conn.execute("PRAGMA user_version = 1")

        if user_version <= 1:  # 数据库初始版本
            with open('src/storage/sql/db_preconfig_v1.sql', 'r', encoding='utf-8') as f:
                init_sql = f.read()
                await conn.executescript(init_sql)

        await conn.commit()

__all__ = ["conn", "init_db"]
