from storage.db_config import conn
from config.logger import logger

def create_user_if_not_exists(telegram_user_id: int) -> None:
    """如果用户不存在则创建新用户"""
    cursor = conn.execute("SELECT COUNT(1) FROM users WHERE telegram_user_id = ?", (telegram_user_id,))
    exists = cursor.fetchone()[0]
    if not exists:
        logger.info(f"创建新用户, Telegram ID: {telegram_user_id}")
        conn.execute("INSERT INTO users (telegram_user_id) VALUES (?)", (telegram_user_id,))
        conn.commit()

def get_user_by_telegram_id(telegram_user_id: int) -> dict | None:
    """通过 Telegram 用户 ID 获取用户信息"""
    cursor = conn.execute("SELECT user_id, telegram_user_id, created_at_utc FROM users WHERE telegram_user_id = ?", (telegram_user_id,))
    row = cursor.fetchone()
    if row:
        return {
            "user_id": row[0],
            "telegram_user_id": row[1],
            "created_at_utc": row[2],
        }
    return None

def get_user_by_id(user_id: int) -> dict | None:
    """通过用户 ID 获取用户信息"""
    cursor = conn.execute("SELECT user_id, telegram_user_id, created_at_utc FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    if row:
        return {
            "user_id": row[0],
            "telegram_user_id": row[1],
            "created_at_utc": row[2],
        }
    return None
