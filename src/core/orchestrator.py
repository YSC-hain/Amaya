from logger import logger
from config.settings import *
from events import bus, E
from datamodel import *
import storage.message as message_storage
import storage.reminder as reminder_storage
import storage.user as user_storage
from utils import *
from llm.openai_client import OpenAIClient
from storage.work_memory import *
from config.prompts import *
from typing import List, Dict
import asyncio
import time

# 注册工具函数
from functions.reminder_func import *
from functions.work_memory_func import *

class Amaya:
    """Amaya核心类"""

    def __init__(self) -> None:
        self.smart_llm_client = OpenAIClient(model=LLM_MAIN_MODEL, inst=CORE_SYSTEM_PROMPT) # ToDo
        self.fast_llm_client = OpenAIClient(model=LLM_FAST_MODEL, inst=CORE_SYSTEM_PROMPT)
    
    async def process_msg(
        self,
        user_id: int,
        append_inst: str | None = None,
        append_world_context: str | None = None,
        allow_tools: bool = True, # 未来应该拓展为“允许使用的工具集”
    ) -> str:
        llm_context: List[Dict[str, str]] | None = None
        # ToDo

        # 获取用户信息
        user_info = await user_storage.get_user_by_id(user_id)

        # 世界信息 ToDo
        world_info = f"{append_world_context or ''}"

        # 未触发的提醒
        optional_reminder_str = ""
        pending_reminders = await reminder_storage.get_pending_reminders_by_user_id(user_id)
        if pending_reminders:
            optional_reminder_str = "\n\n-----\n[Pending Reminders]\n"        
            for r in pending_reminders:
                optional_reminder_str += f"- [{r.reminder_id}] {r.title} (at {utc_min_str_to_user_local_min(r.remind_at_min_utc, user_info.timezone)})\n"

        # 记忆系统
        memory = ""
        memory_groups = await list_memory_groups_by_user_id(user_id)
        for group in memory_groups:
            memory += f"Memory group: {group['title']}\n"
            points = await list_memory_points_by_group_id(group['memory_group_id'])
            for point in points:
                memory += f"- [{point['anchor']}]->{point['content']}\n"
            memory += "---\n\n"

        llm_context = [
            {
                "role": "world",
                "content": f"[Memory Context]\n{memory}\n\n-----\n\n[World Info]\n{world_info}{optional_reminder_str}"
            }
        ]

        # 最近消息
        history = await message_storage.get_recent_messages_by_user_id(user_id, limit=30)
        llm_context += [
            {
                "role": m["role"],
                "content": f"[{utc_str_to_user_local_min(m['created_at_utc'], user_info.timezone)}] {m['content']}"
            } for m in reversed(history)
        ]

        llm_context.insert(-1, {
            "role": "world",
            "content": f"当前时间：{now_user_local_min(user_info.timezone)}"
        })


        start_time = time.perf_counter()
        res = await self.smart_llm_client.generate_response(
            user_id,
            llm_context,
            append_inst,
            allow_tools=allow_tools,
        )
        end_time = time.perf_counter()
        logger.info(f"LLM响应时间: {end_time - start_time:.2f} 秒")

        return res


amaya = Amaya()

@bus.on(E.IO_SEND_MESSAGE)
async def save_message(msg: OutgoingMessage) -> None:
    await message_storage.create_message(msg.user_id, msg.channel_type, "amaya", msg.content)


@bus.on(E.IO_MESSAGE_RECEIVED)
async def handle_incoming_message(msg: IncomingMessage) -> None:
    logger.info(f"处理来自用户 {msg.user_id} 的消息")
    await message_storage.create_message(msg.user_id, msg.channel_type, "user", msg.content)

    res = await amaya.process_msg(msg.user_id)
    
    bus.emit(E.IO_SEND_MESSAGE, OutgoingMessage(
        channel_type = msg.channel_type,
        user_id = msg.user_id,
        content = res,
        channel_context = msg.channel_context,
        metadata = msg.metadata,
    ))


@bus.on(E.REMINDER_TRIGGERED)
async def handle_reminder_triggered(reminder: Reminder):
    logger.info(f"触发 Reminder: id={reminder.reminder_id}, user_id={reminder.user_id}, title={reminder.title}")
    reminder.status = "sent"
    reminder.next_action_at_min_utc = None  # ToDo: 未来可能需要更复杂的状态机设计
    await reminder_storage.update_reminder(reminder)

    reminder_context = (
        "[SYSTEM] 有一个提醒被触发\n"
        f"标题：{reminder.title}\n"
        f"要求：{reminder.prompt}\n"
        "说明：请根据上下文与要求，直接生成要发给用户的提醒消息。"
    )

    res = await amaya.process_msg(
        reminder.user_id,
        append_world_context=reminder_context,
        append_inst="\n现在, 你需要输出一条要发送给用户的提醒消息（语气自然友好、简洁、提醒现在应该做什么）",
        allow_tools=False,
    )

    user_info = await user_storage.get_user_by_id(reminder.user_id)
    if user_info is None:
        logger.error(f"Reminder 发送失败: 找不到用户 user_id={reminder.user_id}")
        return

    if ENABLE_QQ_NAPCAT and user_info.qq_user_id is not None:
        channel_type = ChannelType.QQ_NAPCAT_ONEBOT_V11
    elif ENABLE_TELEGRAM_BOT_POLLING and user_info.telegram_user_id is not None:
        channel_type = ChannelType.TELEGRAM_BOT_POLLING
    else:
        logger.error(
            f"Reminder 发送失败: 用户 user_id={reminder.user_id} 没有可用通道"
            f" (qq_enabled={ENABLE_QQ_NAPCAT}, tg_enabled={ENABLE_TELEGRAM_BOT_POLLING})"
        )
        return

    bus.emit(E.IO_SEND_MESSAGE, OutgoingMessage(
        channel_type = channel_type,
        user_id = reminder.user_id,
        content = res,
        channel_context = None,
    ))
    #bus.emit(E.REMINDER_SENT, reminder_id=reminder.reminder_id)

async def main_loop(shutdown_event: asyncio.Event = asyncio.Event()) -> None:
    """主异步事件循环"""
    logger.info("Orchestrator 主循环已启动")
    while not shutdown_event.is_set():
        #logger.trace("Amaya Tick")
        await asyncio.sleep(1)
    
    logger.info("Orchestrator 已关闭")
