from logger import logger
from config.settings import *
from events import bus, E
from datamodel import *
from storage.work_memory import *
import storage.message as message_storage
import storage.reminder as reminder_storage
from core.amaya import require_amaya

# 注册工具函数
from functions.reminder_func import *
from functions.work_memory_func import *


@bus.on(E.IO_SEND_MESSAGE)
async def save_message(msg: OutgoingMessage) -> None:
    await message_storage.create_message(
        msg.channel_type,
        "amaya",
        msg.content,
        metadata=msg.metadata,
    )


@bus.on(E.IO_MESSAGE_RECEIVED)
async def handle_incoming_message(msg: IncomingMessage) -> None:
    logger.info(f"开始处理来自用户的消息")
    await message_storage.create_message(
        msg.channel_type,
        "user",
        msg.content,
        metadata=msg.metadata,
    )
    amaya = require_amaya()
    amaya.notify_new_message()


@bus.on(E.REMINDER_TRIGGERED)
async def handle_reminder_triggered(reminder: Reminder):
    logger.info(f"触发 Reminder: id={reminder.reminder_id}, title={reminder.title}")
    reminder.status = "triggered"
    reminder.next_action_at_min_utc = None  # ToDo: 未来可能需要更复杂的状态机设计
    await reminder_storage.update_reminder(reminder)

    world_context = (
        "[SYSTEM]{有一个提醒被触发，请注意及时转达给“凛星”: "
        f"{reminder.title} -> {reminder.prompt} }}"
    )
    await message_storage.create_message(
        ChannelType.AMAYA_INTERNAL,
        "world",
        world_context,
        metadata={
            "kind": "reminder_triggered",
            "reminder_id": reminder.reminder_id,
        },
    )
    amaya = require_amaya()
    amaya.notify_new_message()
