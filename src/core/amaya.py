import asyncio
import time
import re
from typing import List

from logger import logger
from config.settings import *
from datamodel import *
from events import bus, E
from llm.base import LLMClient, LLMContextItem
from storage.work_memory import *
import storage.message as message_storage
import storage.reminder as reminder_storage
from utils import *

__all__ = ["Amaya", "configure_amaya", "require_amaya"]


_SEGMENT_MARKER_PATTERN = re.compile(r"^-#(\d+)#-$")

class Amaya:
    """Amaya 单例模块"""

    def __init__(self, smart_llm_client: LLMClient, fast_llm_client: LLMClient | None = None, channel: tuple[ChannelType, dict | None] = None) -> None:
        if channel is None:
            logger.critical("未配置 Amaya 的主联系方式，无法启动！请检查 PRIMARY_CONTACT_METHOD 设置")
            exit(-1)
        self.primary_channel_type: ChannelType = channel[0]
        self.primary_channel_metadata: dict | None = channel[1]

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
                    logger.info("Amaya 收到新消息通知")

                    if self.think_task is not None and not self.think_task.done():
                        self.think_task.cancel()
                        try:
                            await self.think_task
                        except asyncio.CancelledError:
                            logger.info("Amaya 当前思考任务已取消")

                    if self.unsend_messages:
                        logger.info("Amaya 开始重新规划回复")
                        self.unsend_messages_buffer = self.unsend_messages.copy()  # 将当前未发送的消息加载到思考缓存
                        self.unsend_messages = []  # 等待重新规划
                    else:
                        logger.info("Amaya 开始规划回复")

                    self.think_task = asyncio.create_task(
                        self._process_msg(),
                        name="amaya-think",
                    )

                if self.unsend_messages:
                    delay_seconds, segment_text = self.unsend_messages[0]
                    if delay_seconds <= 0:
                        self.unsend_messages.pop(0)
                        #logger.info(f"Amaya 正在发送计划中的消息: `{segment_text}`")
                        bus.emit(
                            E.IO_SEND_MESSAGE,
                            OutgoingMessage(
                                channel_type=self.primary_channel_type,
                                content=segment_text,
                                attachments=None,
                                channel_context=None,
                                metadata=self.primary_channel_metadata,
                            ),
                        )
                    else:
                        self.unsend_messages[0] = (delay_seconds - 1, segment_text)

                await asyncio.sleep(1)
        except asyncio.CancelledError:
            logger.info("Amaya 主循环已停止")
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
        logger.debug(f"LLM API 响应时间: {end_time - start_time:.2f} 秒")

        segments = self._split_segmented_response(res)
        logger.info(f"Amaya 完成回复规划，共 {len(segments)} 段回复")
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


def require_amaya() -> Amaya:
    if _amaya is None:
        raise RuntimeError("Amaya 尚未配置，请先调用 configure_amaya()")
    return _amaya
