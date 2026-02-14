"""
注意: Reminder 的时间(remind_at_min_utc)只精确到分钟，其格式为 "YYYY-MM-DD HH:MM"
"""

from events import bus, E
from logger import logger
from datamodel import *
from typing import Dict, List
from utils import *
import asyncio
import time
import storage.reminder as reminder_storage

__shutdown_event: asyncio.Event = None
__last_check_at_epoch: float | None = None


def get_status() -> dict[str, object]:
    running = __shutdown_event is not None and not __shutdown_event.is_set()
    return {
        "running": running,
        "last_check_at_epoch": __last_check_at_epoch,
    }


async def main_loop(shutdown_event: asyncio.Event):
    global __shutdown_event, __last_check_at_epoch
    __shutdown_event = shutdown_event
    logger.info("Reminder 主循环已启动")
    
    while not shutdown_event.is_set():
        __last_check_at_epoch = time.time()
        reminders_to_process: List[Reminder] = await reminder_storage.get_reminders_need_action_now()
        for reminder in reminders_to_process:
            bus.emit(E.REMINDER_TRIGGERED, reminder=reminder)
            reminder.status = "triggered"
            reminder.next_action_at_min_utc = None
            await reminder_storage.update_reminder(reminder)  # ToDo: 将状态更新放到事件处理器里，并设法完善消息的状态机转换

        await asyncio.sleep(5)  # 每5秒检查一次，可能需要改进

    logger.info("Reminder 主循环已关闭")
