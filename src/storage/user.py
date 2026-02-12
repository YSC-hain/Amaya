import storage.db_config as db_config
from datamodel import *
from logger import logger

def _ensure_conn():
    if db_config.conn is None:
        raise RuntimeError("数据库未初始化，请先调用 init_db()")

async def create_user_if_not_exists(telegram_user_id: int) -> None:
    """如果用户不存在则创建新用户"""
    _ensure_conn()
    async with db_config.conn.execute("SELECT COUNT(1) FROM users WHERE telegram_user_id = ?", (telegram_user_id,)) as cursor:
        row = await cursor.fetchone()
        exists = row[0] if row else 0
    if not exists:
        logger.info(f"创建新用户, Telegram ID: {telegram_user_id}")
        await db_config.conn.execute("INSERT INTO users (telegram_user_id) VALUES (?)", (telegram_user_id,))
        await db_config.conn.commit()

async def get_user_by_telegram_id(telegram_user_id: int) -> UserInfo | None:
    """通过 Telegram 用户 ID 获取用户信息"""
    _ensure_conn()
    async with db_config.conn.execute("SELECT user_id, user_name, timezone, email, telegram_user_id FROM users WHERE telegram_user_id = ?", (telegram_user_id,)) as cursor:
        row = await cursor.fetchone()
        if row:
            return UserInfo(
                user_id=row[0],
                user_name=row[1],
                timezone=row[2],
                email=row[3],
                telegram_user_id=row[4],
            )
        else:
            return None

async def get_user_by_id(user_id: int) -> UserInfo | None:
    """通过用户 ID 获取用户信息"""
    _ensure_conn()
    async with db_config.conn.execute("SELECT user_id, user_name, timezone, email, telegram_user_id FROM users WHERE user_id = ?", (user_id,)) as cursor:
        row = await cursor.fetchone()
        if row:
            return UserInfo(
                user_id=row[0],
                user_name=row[1],
                timezone=row[2],
                email=row[3],
                telegram_user_id=row[4]
            )
        else:
            return None
