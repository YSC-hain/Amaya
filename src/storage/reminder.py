import storage.db_config as db_config
from config.logger import logger
from datamodel.reminder_base import *
from events import bus, E
import datetime

def _ensure_conn():
    if db_config.conn is None:
        raise RuntimeError("数据库未初始化，请先调用 init_db()")

async def create_reminder(user_id: int, title: str, remind_at_utc: str, prompt: str) -> Reminder:
    """创建提醒"""
    _ensure_conn()
    async with db_config.conn.execute(
        "INSERT INTO reminders (user_id, title, remind_at_utc, prompt, status, next_action_at_utc) VALUES (?, ?, ?, ?, ?, ?)",
        (user_id, title, remind_at_utc, prompt, "pending", remind_at_utc)
    ) as cursor:
        await db_config.conn.commit()
        reminder_id = cursor.lastrowid
        bus.emit(E.REMINDER_CREATED, reminder_id=reminder_id, user_id=user_id, title=title, remind_at_utc=remind_at_utc, prompt=prompt)
        logger.trace(f"创建提醒: user_id={user_id}, title={title}, remind_at_utc={remind_at_utc}, reminder_id={reminder_id}")
        return Reminder(
            reminder_id=reminder_id,
            user_id=user_id,
            title=title,
            remind_at_utc=remind_at_utc,
            prompt=prompt,
            status="pending",
            next_action_at_utc=remind_at_utc
        )

async def get_pending_reminders() -> list[Reminder]:
    """获取所有未触发的提醒"""
    _ensure_conn()
    async with db_config.conn.execute(
        "SELECT reminder_id, user_id, title, remind_at_utc, prompt, status, next_action_at_utc FROM reminders WHERE status = 'pending'"
    ) as cursor:
        rows = await cursor.fetchall()
        return [
            Reminder(
                reminder_id=row[0],
                user_id=row[1],
                title=row[2],
                remind_at_utc=row[3],
                prompt=row[4],
                status=row[5],
                next_action_at_utc=row[6]
            )
            for row in rows
        ]

async def get_reminders_need_action_now() -> list[Reminder]:
    """获取所有需要立即执行后续动作的提醒"""
    _ensure_conn()
    now_utc = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    async with db_config.conn.execute(
        "SELECT reminder_id, user_id, title, remind_at_utc, prompt, status, next_action_at_utc FROM reminders WHERE (next_action_at_utc NOT NULL) AND next_action_at_utc <= ?",
        (now_utc,)
    ) as cursor:
        rows = await cursor.fetchall()
        return [
            Reminder(
                reminder_id=row[0],
                user_id=row[1],
                title=row[2],
                remind_at_utc=row[3],
                prompt=row[4],
                status=row[5],
                next_action_at_utc=row[6]
            )
            for row in rows
        ]


async def update_reminder(reminder: Reminder) -> None:
    """更新提醒状态与下次行动时间"""
    _ensure_conn()
    await db_config.conn.execute(
        "UPDATE reminders SET status = ?, next_action_at_utc = ?, updated_at_utc = CURRENT_TIMESTAMP WHERE reminder_id = ?",
        (reminder.status, reminder.next_action_at_utc, reminder.reminder_id)
    )
    await db_config.conn.commit()
    logger.trace(f"更新提醒: reminder_id={reminder.reminder_id}, next_action_at_utc={reminder.next_action_at_utc}, status={reminder.status}")
