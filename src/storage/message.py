import storage.db_config as db_config
from logger import logger
from ulid import ULID
import json
from typing import Any

__all__ = [
    "create_message",
    "get_recent_messages",
    "get_message_by_id",
    "get_latest_route",
]


def _ensure_conn():
    if db_config.conn is None:
        raise RuntimeError("数据库未初始化，请先调用 init_db()")

def _loads_metadata(raw_metadata: str | None) -> dict[str, Any] | None:
    if raw_metadata is None or raw_metadata.strip() == "":
        return None
    try:
        loaded = json.loads(raw_metadata)
    except json.JSONDecodeError:
        logger.warning("消息 metadata 解析失败，已忽略")
        return None
    return loaded if isinstance(loaded, dict) else None


async def create_message(
    channel: str,
    role: str,
    content: str,
    metadata: dict[str, Any] | None = None,
) -> str:
    """创建新消息记录，返回消息 ID"""
    _ensure_conn()
    if role not in ("system", "world", "user", "amaya"):
        logger.error(f"无效的消息角色: {role}, 该消息不会存入数据库")
        return ""

    message_id = str(ULID())
    metadata_json = json.dumps(metadata, ensure_ascii=False) if metadata is not None else None
    await db_config.conn.execute(
        "INSERT INTO messages (message_id, channel, metadata, role, content) VALUES (?, ?, ?, ?, ?)",
        (message_id, channel, metadata_json, role, content)
    )
    await db_config.conn.commit()
    return message_id

async def get_recent_messages(limit: int = 50) -> list[dict]:
    """获取最近的消息记录，按 ULID 排列"""
    _ensure_conn()
    messages = []
    async with db_config.conn.execute(
        (
            "SELECT message_id, channel, metadata, role, content, created_at_utc "
            "FROM messages ORDER BY message_id DESC LIMIT ?"
        ),
        (limit,)
    ) as cursor:
        async for row in cursor:
            messages.append({
                "message_id": row[0],
                "channel": row[1],
                "metadata": _loads_metadata(row[2]),
                "role": row[3],
                "content": row[4],
                "created_at_utc": row[5],
            })
    return messages


async def get_message_by_id(message_id: str) -> dict | None:
    """通过消息 ID 获取单条消息"""
    _ensure_conn()
    async with db_config.conn.execute(
        (
            "SELECT message_id, channel, metadata, role, content, created_at_utc "
            "FROM messages WHERE message_id = ? LIMIT 1"
        ),
        (message_id,)
    ) as cursor:
        row = await cursor.fetchone()

    if row is None:
        return None

    return {
        "message_id": row[0],
        "channel": row[1],
        "metadata": _loads_metadata(row[2]),
        "role": row[3],
        "content": row[4],
        "created_at_utc": row[5],
    }


async def get_latest_route() -> dict | None:
    """获取最近一条 user 消息的路由信息"""
    _ensure_conn()
    async with db_config.conn.execute(
        (
            "SELECT channel, metadata, created_at_utc "
            "FROM messages "
            "WHERE role = 'user' "
            "ORDER BY message_id DESC LIMIT 1"
        ),
    ) as cursor:
        row = await cursor.fetchone()

    if row is None:
        return None

    return {
        "channel": row[0],
        "metadata": _loads_metadata(row[1]),
        "created_at_utc": row[2],
    }
