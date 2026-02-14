"""工作记忆存储 v0.1

工作记忆的设计原则是简单可靠。在此划分为两层的架构：
1. 记忆组: 类似文件夹的结构，方便 LLM 组织记忆；
2. 记忆点：具体的记忆信息，字典结构，键代表“记忆锚点”，值代表“记忆内容”
"""

import storage.db_config as db_config
from logger import logger

def _ensure_conn():
    if db_config.conn is None:
        raise RuntimeError("数据库未初始化，请先调用 init_db()")


async def create_memory_group(title: str) -> int:
    """创建记忆组，返回记忆组 ID"""
    _ensure_conn()
    async with db_config.conn.execute(
        "SELECT COUNT(*) FROM memory_groups WHERE title = ?",
        (title,)
    ) as cursor:
        row = await cursor.fetchone()
        if row[0] > 0:
            logger.warning(f"LLM 试图创建已存在的记忆组: title={title}")
            return -1

    async with db_config.conn.execute(
        "INSERT INTO memory_groups (title) VALUES (?)",
        (title,)
    ) as cursor:
        await db_config.conn.commit()
        group_id = cursor.lastrowid
        logger.trace(f"创建记忆组: title={title}, memory_group_id={group_id}")
        return group_id


async def list_memory_groups() -> list[dict]:
    """列出所有记忆组"""
    _ensure_conn()
    groups = []
    async with db_config.conn.execute(
        "SELECT memory_group_id, title, created_at_utc FROM memory_groups"
    ) as cursor:
        async for row in cursor:
            groups.append({
                "memory_group_id": row[0],
                "title": row[1],
                "created_at_utc": row[2],
            })
    return groups


async def edit_memory_group_title_by_id(memory_group_id: int, new_title: str) -> None:
    """修改记忆组标题"""
    _ensure_conn()
    await db_config.conn.execute(
        "UPDATE memory_groups SET title = ? WHERE memory_group_id = ?",
        (new_title, memory_group_id)
    )
    await db_config.conn.commit()
    logger.trace(f"修改记忆组标题: memory_group_id={memory_group_id}, new_title={new_title}")


async def delete_memory_group_by_id(memory_group_id: int) -> None:
    """删除记忆组及其下所有记忆点"""
    _ensure_conn()
    await db_config.conn.execute(
        "DELETE FROM memory_points WHERE memory_group_id = ?",
        (memory_group_id,)
    )
    await db_config.conn.execute(
        "DELETE FROM memory_groups WHERE memory_group_id = ?",
        (memory_group_id,)
    )
    await db_config.conn.commit()
    logger.trace(f"删除记忆组及其记忆点: memory_group_id={memory_group_id}")



async def create_memory_point(memory_group_title: str, anchor: str, content: str, memory_type: str, weight: float) -> int:
    """添加记忆点，返回记忆点 ID"""
    _ensure_conn()
    async with db_config.conn.execute(
        "SELECT memory_group_id FROM memory_groups WHERE title = ?",
        (memory_group_title,)
    ) as cursor:
        row = await cursor.fetchone()
        if row is None:
            logger.error(f"LLM 试图在不存在的记忆组中添加记忆点: memory_group_title={memory_group_title}")
            return -1
        memory_group_id = row[0]

    async with db_config.conn.execute(
        "INSERT INTO memory_points (memory_group_id, anchor, content, memory_type, weight) VALUES (?, ?, ?, ?, ?)",
        (memory_group_id, anchor, content, memory_type, weight)
    ) as cursor:
        await db_config.conn.commit()
        point_id = cursor.lastrowid
        logger.trace(f"添加记忆点: memory_group_id={memory_group_id}, anchor={anchor}, point_id={point_id}, memory_type={memory_type}, weight={weight}")
        return point_id


async def edit_memory_point_weight_by_id(memory_point_id: int, new_weight: float) -> None:
    """修改记忆点权重"""
    _ensure_conn()
    await db_config.conn.execute(
        "UPDATE memory_points SET weight = ? WHERE memory_point_id = ?",
        (new_weight, memory_point_id)
    )
    await db_config.conn.commit()
    logger.trace(f"修改记忆点权重: memory_point_id={memory_point_id}, new_weight={new_weight}")


async def edit_memory_point_content_by_id(memory_point_id: int, new_content: str) -> bool:
    """修改记忆点内容"""
    _ensure_conn()
    async with db_config.conn.execute(
        "SELECT COUNT(*) FROM memory_points WHERE memory_point_id = ?",
        (memory_point_id,)
    ) as cursor:
        row = await cursor.fetchone()
        if row[0] == 0:
            logger.error(f"LLM 试图修改不存在的记忆点内容: memory_point_id={memory_point_id}")
            return False

    await db_config.conn.execute(
        "UPDATE memory_points SET content = ? WHERE memory_point_id = ?",
        (new_content, memory_point_id)
    )
    await db_config.conn.commit()
    logger.trace(f"修改记忆点内容: memory_point_id={memory_point_id}, new_content={new_content}")
    return True


async def list_memory_points_by_group_id(memory_group_id: int) -> list[dict]:
    """列出记忆组下的所有记忆点"""
    _ensure_conn()
    points = []
    async with db_config.conn.execute(
        "SELECT memory_point_id, anchor, content, memory_type, weight, created_at_utc FROM memory_points WHERE memory_group_id = ?",
        (memory_group_id,)
    ) as cursor:
        async for row in cursor:
            points.append({
                "memory_point_id": row[0],
                "anchor": row[1],
                "content": row[2],
                "memory_type": row[3],
                "weight": row[4],
                "created_at_utc": row[5],
            })
    return points
