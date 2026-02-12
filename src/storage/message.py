import storage.db_config as db_config
from logger import logger
from ulid import ULID

__all__ = ["create_message", "get_recent_messages_by_user_id"]


def _ensure_conn():
    if db_config.conn is None:
        raise RuntimeError("数据库未初始化，请先调用 init_db()")

async def create_message(user_id: int, channel: str, role: str, content: str) -> int:
    """创建新消息记录，返回消息 ID"""
    _ensure_conn()
    if role not in ("user", "amaya", "assistant"):
        logger.error(f"无效的消息角色: {role}, 该消息不会存入数据库")
        return

    message_id = str(ULID())
    await db_config.conn.execute(
        "INSERT INTO messages (message_id, user_id, channel, role, content) VALUES (?, ?, ?, ?, ?)",
        (message_id, user_id, channel, role, content)
    )
    await db_config.conn.commit()
    return message_id

async def get_recent_messages_by_user_id(user_id: int, limit: int = 50) -> list[dict]:
    """通过用户 ID 获取消息记录，按 ULID 排列"""
    _ensure_conn()
    messages = []
    async with db_config.conn.execute(
        "SELECT message_id, user_id, channel, role, content, created_at_utc FROM messages WHERE user_id = ? ORDER BY message_id DESC LIMIT ?",
        (user_id, limit)
    ) as cursor:
        async for row in cursor:
            messages.append({
                "message_id": row[0],
                "user_id": row[1],
                "channel": row[2],
                "role": row[3],
                "content": row[4],
                "created_at_utc": row[5],
            })
    return messages
