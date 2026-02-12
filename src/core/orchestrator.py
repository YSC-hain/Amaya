from config.logger import logger
from config.settings import *
from events import bus, E
from datamodel.reminder_base import *
from channels.base import ChannelType, IncomingMessage, OutgoingMessage
import storage.message as message_storage
import storage.reminder as reminder_storage
from llm.openai_client import OpenAIClient
from storage.work_memory import *
from config.prompts import *
from typing import List, Dict
import asyncio
import time
import datetime

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
                "content": f"[Memory Context]\n{memory}"
            }
        ]

        # 最近消息
        history = await message_storage.get_recent_messages_by_user_id(user_id, limit=30)
        llm_context += [ {"role": m["role"], "content": m["content"]} for m in reversed(history) ]

        # 世界信息
        world_info = f"Current Time: {datetime.datetime.now()}\n{append_world_context or ''}"
        llm_context.append({
            "role": "world",
            "content": f"[World Info]\n{world_info}"
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
    ))


@bus.on(E.REMINDER_TRIGGERED)
async def handle_reminder_triggered(reminder: Reminder):
    logger.info(f"触发 Reminder: id={reminder.reminder_id}, user_id={reminder.user_id}, title={reminder.title}")

    # 提醒触发属于“事件通知”，必须避免再次产生副作用（例如又创建一个 reminder）
    reminder_context = (
        "[SYSTEM] 提醒被触发\n"
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
    bus.emit(E.IO_SEND_MESSAGE, OutgoingMessage(
        channel_type = ChannelType.TELEGRAM_BOT_POLLING,  # ToDo
        user_id = reminder.user_id,
        content = res,
        channel_context = None,
    ))
    #bus.emit(E.REMINDER_SENT, reminder_id=reminder.reminder_id)
    reminder.status = "sent"
    reminder.next_action_at_utc = None
    await reminder_storage.update_reminder(reminder)

async def main_loop(shutdown_event: asyncio.Event = asyncio.Event()) -> None:
    """主异步事件循环"""
    logger.info("Orchestrator 主循环已启动")
    while not shutdown_event.is_set():
        #logger.trace("Amaya Tick")
        await asyncio.sleep(1)
    
    logger.info("关闭 Orchestrator")
