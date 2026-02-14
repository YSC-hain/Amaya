import asyncio
import re
import time
from typing import List

from logger import logger
from config.settings import *
from events import bus, E
from datamodel import *
import storage.message as message_storage
import storage.reminder as reminder_storage
from utils import *
from llm.base import LLMClient, LLMContextItem
from storage.work_memory import *
from config.prompts import *

# 注册工具函数
from functions.reminder_func import *
from functions.work_memory_func import *

_SEGMENT_MARKER_PATTERN = re.compile(r"^-#(\d+)#-$")


def _get_primary_channel() -> tuple[ChannelType, dict | None]:
    """获取主联系方式对应的通道"""
    if PRIMARY_CONTACT_METHOD == "telegram":
        return ChannelType.TELEGRAM_BOT_POLLING, None
    elif PRIMARY_CONTACT_METHOD == "qq":
        return ChannelType.QQ_NAPCAT_ONEBOT_V11, None
    else:
        raise ValueError(f"不支持的主联系方式: {PRIMARY_CONTACT_METHOD}")


class Amaya:
    """Amaya 单例模块"""

    def __init__(self, smart_llm_client: LLMClient, fast_llm_client: LLMClient | None = None) -> None:
        self.smart_llm_client = smart_llm_client
        self.fast_llm_client = fast_llm_client or smart_llm_client

        self.get_new_msg_event = asyncio.Event()
        self.unsend_messages: list[tuple[int, str]] = []
        self.unsend_messages_buffer: list[tuple[int, str]] = []  # 类似人脑的“短期记忆”，是Amaya的思考缓存
        self.think_task: asyncio.Task[None] | None = None

    def notify_new_message(self) -> None:
        self.get_new_msg_event.set()

    async def run_loop(self, shutdown_event: asyncio.Event) -> None:
        logger.info("Amaya 主循环已启动")
        try:
            while not shutdown_event.is_set():
                if self.get_new_msg_event.is_set():
                    self.get_new_msg_event.clear()

                    if self.think_task is not None and not self.think_task.done():
                        logger.info("Amaya 在思考时收到新消息，尝试中断思考")
                        self.think_task.cancel()
                        try:
                            await self.think_task
                        except asyncio.CancelledError:
                            logger.info("Amaya 当前思考任务已取消")

                    if self.unsend_messages:
                        logger.info("开始重新规划回复")
                        self.unsend_messages_buffer = self.unsend_messages.copy()  # 将当前未发送的消息加载到思考缓存
                        self.unsend_messages = []  # 等待重新规划
                    
                    self.think_task = asyncio.create_task(
                        self._process_msg(),
                        name="amaya-think",
                    )

                if self.unsend_messages:
                    delay_seconds, segment_text = self.unsend_messages[0]
                    if delay_seconds <= 0:
                        self.unsend_messages.pop(0)
                        channel_type, metadata = _get_primary_channel()
                        #logger.info(f"Amaya 正在发送计划中的消息: `{segment_text}`")
                        bus.emit(
                            E.IO_SEND_MESSAGE,
                            OutgoingMessage(
                                channel_type=channel_type,
                                content=segment_text,
                                attachments=None,
                                channel_context=None,
                                metadata=metadata,
                            ),
                        )
                    else:
                        self.unsend_messages[0] = (delay_seconds - 1, segment_text)

                await asyncio.sleep(1)
        except asyncio.CancelledError:
            logger.info("Amaya worker 已停止")
            return

    async def _process_msg(
        self,
        append_inst: str | None = None,
        append_world_context: str | None = None,
        allow_tools: bool = True   # 未来应该拓展为“允许使用的工具集”
    ) -> None:
        llm_context: List[LLMContextItem] | None = None

        # 世界信息 ToDo
        world_info = f"{append_world_context or ''}"

        # 未触发的提醒
        optional_reminder_str = ""
        pending_reminders = await reminder_storage.get_pending_reminders()
        if pending_reminders:
            optional_reminder_str = "\n\n-----\n[Pending Reminders]\n"
            for r in pending_reminders:
                optional_reminder_str += (
                    f"- [{r.reminder_id}] {r.title} "
                    f"(at {utc_min_str_to_user_local_min(r.remind_at_min_utc, USER_TIMEZONE)})\n"
                )

        # 记忆系统
        memory = ""
        memory_groups = await list_memory_groups()
        for group in memory_groups:
            memory += f"Memory group: {group['title']}{{\n"
            points = await list_memory_points_by_group_id(group["memory_group_id"])
            for point in points:
                memory += f"- [{point['anchor']}]->{point['content']}\n"
            memory += "}\n\n-----\n"

        llm_context = [
            {
                "role": "world",
                "content": f"[Memory Context]\n{memory}\n\n-----\n\n[World Info]\n{world_info}{optional_reminder_str}",
            }
        ]

        # 最近消息
        history = await message_storage.get_recent_messages(limit=30)
        llm_context += [
            {
                "role": m["role"],
                "content": f"[{utc_str_to_user_local_min(m['created_at_utc'], USER_TIMEZONE)}] {m['content']}",
            }
            for m in reversed(history)
        ]

        # 世界消息，固定位于倒数第二条以辅助模型判断，包含当前时间与提醒信息等
        special_world_content = f"当前时间：{now_user_local_min(USER_TIMEZONE)}"
        if append_world_context:
            special_world_content += f"\n{append_world_context}"
        if self.unsend_messages_buffer:
            special_world_content += "\n\n[Amaya Context]这是在下面一条“凛星”的消息之前, Amaya原本想要发送的内容:{\n"
            for _, msg in self.unsend_messages_buffer:
                special_world_content += f"- {msg}\n"
            special_world_content += "}\n"
        llm_context.insert(-1, {
            "role": "world",
            "content": special_world_content
        })

        start_time = time.perf_counter()
        res = await self.smart_llm_client.generate_response(
            llm_context,
            append_inst,
            allow_tools,
        )
        end_time = time.perf_counter()
        logger.info(f"LLM响应时间: {end_time - start_time:.2f} 秒")

        segments = self._split_segmented_response(res)
        logger.info(f"Amaya 完成回复规划: segment_count={len(segments)}")
        self.unsend_messages = segments
        self.unsend_messages_buffer = segments.copy()  # 同步更新思考缓存


    def _split_segmented_response(self, raw: str) -> list[tuple[int, str]]:
        segments: list[tuple[int, str]] = []
        pending_delay_seconds = 0
        current_lines: list[str] = []

        def flush_current_segment() -> None:
            nonlocal pending_delay_seconds, current_lines

            segment_text = "\n".join(current_lines)
            current_lines = []
            if segment_text.strip():
                segments.append((pending_delay_seconds, segment_text))
            pending_delay_seconds = 0

        for line in raw.splitlines():
            marker_match = _SEGMENT_MARKER_PATTERN.fullmatch(line.strip())  # 控制符格式为 `-#<数字>#-`，例如 `-#3#-`` 表示接下来要发送的消息需要在前一条消息发送后等待3秒。
            if marker_match is not None:
                if current_lines:
                    flush_current_segment()
                pending_delay_seconds += int(marker_match.group(1)) + int(len(line) * 0.70)  # 模拟打字时间，平均每个字符0.7秒，约等于85字/分钟
                continue

            current_lines.append(line)

        if current_lines:
            flush_current_segment()

        if not segments:
            logger.warning(
                f"要发送给用户 {self.user_id} 的消息在分段解析后无可发送段落，回退为原文单段发送: raw_len={len(raw)}"
            )
            return [(0, raw)]

        return segments


_amaya: Amaya | None = None


def configure_amaya(amaya: Amaya) -> None:
    global _amaya
    _amaya = amaya


def _require_amaya() -> Amaya:
    if _amaya is None:
        raise RuntimeError("Amaya 尚未配置，请先调用 configure_amaya()")
    return _amaya


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
    amaya = _require_amaya()
    amaya.notify_new_message()


@bus.on(E.REMINDER_TRIGGERED)
async def handle_reminder_triggered(reminder: Reminder):
    logger.info(f"触发 Reminder: id={reminder.reminder_id}, title={reminder.title}")
    reminder.status = "triggered"
    reminder.next_action_at_min_utc = None  # ToDo: 未来可能需要更复杂的状态机设计
    await reminder_storage.update_reminder(reminder)

    channel_type, metadata = _get_primary_channel()
    world_context = (
        "[SYSTEM]{有一个提醒被触发，请注意及时转达给“凛星”: "
        f"{reminder.title} -> {reminder.prompt} }}"
    )
    await message_storage.create_message(
        channel_type,
        "world",
        world_context,
        metadata={
            "kind": "reminder_triggered",
            "reminder_id": reminder.reminder_id,
        },
    )

    amaya = _require_amaya()
    amaya.notify_new_message()
