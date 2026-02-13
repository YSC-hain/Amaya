import storage.db_config as db_config
from datamodel import *
from logger import logger


def _ensure_conn():
    if db_config.conn is None:
        raise RuntimeError("数据库未初始化，请先调用 init_db()")


def _row_to_user(row) -> UserInfo:
    return UserInfo(
        user_id=row[0],
        user_name=row[1],
        timezone=row[2],
        email=row[3],
        telegram_user_id=row[4],
        qq_user_id=row[5],
    )


async def create_user_if_not_exists(telegram_user_id: int) -> None:
    """如果 Telegram 用户不存在则创建新用户"""
    _ensure_conn()
    async with db_config.conn.execute("SELECT COUNT(1) FROM users WHERE telegram_user_id = ?", (telegram_user_id,)) as cursor:
        row = await cursor.fetchone()
        exists = row[0] if row else 0
    if not exists:
        logger.info(f"创建新用户, Telegram ID: {telegram_user_id}")
        await db_config.conn.execute("INSERT INTO users (telegram_user_id) VALUES (?)", (telegram_user_id,))
        await db_config.conn.commit()


async def create_user_if_not_exists_by_qq(qq_user_id: int) -> None:
    """如果 QQ 用户不存在则创建新用户"""
    _ensure_conn()
    async with db_config.conn.execute("SELECT COUNT(1) FROM users WHERE qq_user_id = ?", (qq_user_id,)) as cursor:
        row = await cursor.fetchone()
        exists = row[0] if row else 0
    if not exists:
        logger.info(f"创建新用户, QQ ID: {qq_user_id}")
        await db_config.conn.execute("INSERT INTO users (qq_user_id) VALUES (?)", (qq_user_id,))
        await db_config.conn.commit()


async def get_user_by_telegram_id(telegram_user_id: int) -> UserInfo | None:
    """通过 Telegram 用户 ID 获取用户信息"""
    _ensure_conn()
    async with db_config.conn.execute(
        "SELECT user_id, user_name, timezone, email, telegram_user_id, qq_user_id FROM users WHERE telegram_user_id = ?",
        (telegram_user_id,),
    ) as cursor:
        row = await cursor.fetchone()
        return _row_to_user(row) if row else None


async def get_user_by_qq_id(qq_user_id: int) -> UserInfo | None:
    """通过 QQ 用户 ID 获取用户信息"""
    _ensure_conn()
    async with db_config.conn.execute(
        "SELECT user_id, user_name, timezone, email, telegram_user_id, qq_user_id FROM users WHERE qq_user_id = ?",
        (qq_user_id,),
    ) as cursor:
        row = await cursor.fetchone()
        return _row_to_user(row) if row else None


async def get_user_by_id(user_id: int) -> UserInfo | None:
    """通过用户 ID 获取用户信息"""
    _ensure_conn()
    async with db_config.conn.execute(
        "SELECT user_id, user_name, timezone, email, telegram_user_id, qq_user_id FROM users WHERE user_id = ?",
        (user_id,),
    ) as cursor:
        row = await cursor.fetchone()
        return _row_to_user(row) if row else None
