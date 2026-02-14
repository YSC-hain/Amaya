from dataclasses import dataclass
import asyncio
import re
import time
from typing import List, Literal, cast

from logger import logger
from config.settings import *
from events import bus, E
from datamodel import *
import storage.message as message_storage
import storage.reminder as reminder_storage
import storage.user as user_storage
from utils import *
from llm.base import LLMClient, LLMContextItem
from storage.work_memory import *
from config.prompts import *

# 注册工具函数
from functions.reminder_func import *
from functions.work_memory_func import *


@dataclass
class AmayaTask:
    task_type: Literal["incoming_message", "reminder_triggered"]
    payload: IncomingMessage | Reminder


class Amaya:
    """单用户 Amaya 实例"""

    def __init__(self, user_id: int, smart_llm_client: LLMClient, fast_llm_client: LLMClient | None = None) -> None:
        self.user_id = user_id
        self.smart_llm_client = smart_llm_client
        self.fast_llm_client = fast_llm_client or smart_llm_client
        self.unread_queue: asyncio.Queue[AmayaTask] = asyncio.Queue()

    async def run_loop(self) -> None:
        logger.info(f"用户 {self.user_id} 的 Amaya worker 已启动")
        try:
            while True:
                task = await self.unread_queue.get()
                try:
                    await self._process_with_retry(task)
                finally:
                    self.unread_queue.task_done()
        except asyncio.CancelledError:
            logger.info(f"用户 {self.user_id} 的 Amaya worker 已停止")
            raise

    def enqueue_task(self, task: AmayaTask) -> None:
        self.unread_queue.put_nowait(task)
        logger.trace(
            f"用户 {self.user_id} 任务入队: task_type={task.task_type}, queue_size={self.unread_queue.qsize()}"
        )

    async def _process_with_retry(self, task: AmayaTask) -> None:
        max_attempts = 3
        for attempt in range(1, max_attempts + 1):
            try:
                await self._dispatch_task(task)
                return
            except Exception as e:
                if attempt >= max_attempts:
                    logger.error(
                        f"用户 {self.user_id} 任务处理失败且超过重试次数: task_type={task.task_type}",
                        exc_info=e,
                    )
                    return

                delay_seconds = 2 ** (attempt - 1)
                logger.warning(
                    f"用户 {self.user_id} 任务处理失败，准备重试: "
                    f"task_type={task.task_type}, attempt={attempt}/{max_attempts}, sleep={delay_seconds}s, error={e}"
                )
                await asyncio.sleep(delay_seconds)

    async def _dispatch_task(self, task: AmayaTask) -> None:
        """调度任务到具体处理函数"""
        if task.task_type == "incoming_message":
            await self._handle_incoming_message(cast(IncomingMessage, task.payload))
            return

        if task.task_type == "reminder_triggered":
            await self._handle_reminder(cast(Reminder, task.payload))
            return

        logger.error(f"未知的任务类型: {task.task_type}")

    async def _process_msg(
        self,
        append_inst: str | None = None,
        append_world_context: str | None = None,
        allow_tools: bool = True,   # 未来应该拓展为“允许使用的工具集”
    ) -> str:
        llm_context: List[LLMContextItem] | None = None

        # 获取用户信息
        user_info = await user_storage.get_user_by_id(self.user_id)
        if user_info is None:
            raise ValueError(f"找不到用户: user_id={self.user_id}")

        # 世界信息 ToDo
        world_info = f"{append_world_context or ''}"

        # 未触发的提醒
        optional_reminder_str = ""
        pending_reminders = await reminder_storage.get_pending_reminders_by_user_id(self.user_id)
        if pending_reminders:
            optional_reminder_str = "\n\n-----\n[Pending Reminders]\n"
            for r in pending_reminders:
                optional_reminder_str += (
                    f"- [{r.reminder_id}] {r.title} "
                    f"(at {utc_min_str_to_user_local_min(r.remind_at_min_utc, user_info.timezone)})\n"
                )

        # 记忆系统
        memory = ""
        memory_groups = await list_memory_groups_by_user_id(self.user_id)
        for group in memory_groups:
            memory += f"Memory group: {group['title']}\n"
            points = await list_memory_points_by_group_id(group["memory_group_id"])
            for point in points:
                memory += f"- [{point['anchor']}]->{point['content']}\n"
            memory += "---\n\n"

        llm_context = [
            {
                "role": "world",
                "content": f"[Memory Context]\n{memory}\n\n-----\n\n[World Info]\n{world_info}{optional_reminder_str}",
            }
        ]

        # 最近消息
        history = await message_storage.get_recent_messages_by_user_id(self.user_id, limit=30)
        llm_context += [
            {
                "role": m["role"],
                "content": f"[{utc_str_to_user_local_min(m['created_at_utc'], user_info.timezone)}] {m['content']}",
            }
            for m in reversed(history)
        ]

        llm_context.insert(-1, {
            "role": "world",
            "content": f"当前时间：{now_user_local_min(user_info.timezone)}"
        })


        start_time = time.perf_counter()
        res = await self.smart_llm_client.generate_response(
            self.user_id,
            llm_context,
            append_inst,
            allow_tools=allow_tools,
        )
        end_time = time.perf_counter()
        logger.info(f"LLM响应时间: {end_time - start_time:.2f} 秒")

        return res

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
            marker_match = re.compile(r"^-#(\d+)#-$").fullmatch(line.strip())  # 控制符格式为 `-#<数字>#-`，例如 `-#3#-`` 表示接下来要发送的消息需要在前一条消息发送后等待3秒。
            if marker_match is not None:
                if current_lines:
                    flush_current_segment()
                pending_delay_seconds += int(marker_match.group(1))
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

    async def _emit_segmented_message(
        self,
        base_message: OutgoingMessage,
        segments: list[tuple[int, str]],
    ) -> None:
        logger.info(
            f" 即将分段发送消息给用户 {self.user_id}: segment_count={len(segments)}, channel={base_message.channel_type}"
        )

        # ToDo: 若新消息在分段发送期间到来，应中断当前发送并重新思考回复。
        for idx, (delay_seconds, segment_text) in enumerate(segments, start=1):
            if delay_seconds > 0:
                logger.trace(
                    f"用户 {self.user_id} 分段发送等待: segment={idx}/{len(segments)}, delay={delay_seconds}s"
                )
                await asyncio.sleep(delay_seconds)

            logger.info(
                f"向用户 {self.user_id} 发送分段消息: segment={idx}/{len(segments)}, "
                f"delay={delay_seconds}s, text_len={len(segment_text)}"
            )
            bus.emit(
                E.IO_SEND_MESSAGE,
                OutgoingMessage(
                    channel_type=base_message.channel_type,
                    user_id=base_message.user_id,
                    content=segment_text,
                    attachments=base_message.attachments,
                    channel_context=base_message.channel_context,
                    metadata=base_message.metadata,
                ),
            )

    async def _handle_incoming_message(self, msg: IncomingMessage) -> None:
        logger.info(f"处理来自用户 {self.user_id} 的入队消息")
        # ToDo: 未来可升级为“短时间窗聚合未读消息”，以实现更拟人的连续对话体验。
        res = await self._process_msg()
        segments = self._split_segmented_response(res)
        await self._emit_segmented_message(
            OutgoingMessage(
                channel_type=msg.channel_type,
                user_id=self.user_id,
                content="",  # 实际发送内容在分段循环内逐段填充
                channel_context=msg.channel_context,
                metadata=msg.metadata,
            ),
            segments,
        )

    async def _handle_reminder(self, reminder: Reminder) -> None:
        logger.info(
            f"处理用户 {self.user_id} 的提醒任务: reminder_id={reminder.reminder_id}, title={reminder.title}"
        )

        reminder_context = (
            "[SYSTEM] 有一个提醒被触发\n"
            f"标题：{reminder.title}\n"
            f"要求：{reminder.prompt}\n"
            "说明：请根据上下文与要求，直接生成要发给用户的提醒消息。"
        )

        res = await self._process_msg(
            append_world_context=reminder_context,
            append_inst="\n现在, 你需要输出一条要发送给用户的提醒消息（语气自然友好、简洁、提醒现在应该做什么）",
            allow_tools=True,  # 还是得允许使用工具
        )

        user_info = await user_storage.get_user_by_id(self.user_id)
        if user_info is None:
            logger.error(f"Reminder 发送失败: 找不到用户 user_id={self.user_id}")
            return

        if ENABLE_QQ_NAPCAT and user_info.qq_user_id is not None:
            channel_type = ChannelType.QQ_NAPCAT_ONEBOT_V11
        elif ENABLE_TELEGRAM_BOT_POLLING and user_info.telegram_user_id is not None:
            channel_type = ChannelType.TELEGRAM_BOT_POLLING
        else:
            logger.error(
                f"Reminder 发送失败: 用户 user_id={self.user_id} 没有可用通道"
                f" (qq_enabled={ENABLE_QQ_NAPCAT}, tg_enabled={ENABLE_TELEGRAM_BOT_POLLING})"
            )
            return

        segments = self._split_segmented_response(res)
        await self._emit_segmented_message(
            OutgoingMessage(
                channel_type=channel_type,
                user_id=self.user_id,
                content="",  # 实际发送内容在分段循环内逐段填充
                channel_context=None,
            ),
            segments,
        )


class AmayaManager:
    def __init__(self, smart_llm_client: LLMClient, fast_llm_client: LLMClient | None = None) -> None:
        self.smart_llm_client = smart_llm_client
        self.fast_llm_client = fast_llm_client or smart_llm_client
        self._instances: dict[int, Amaya] = {}
        self._workers: dict[int, asyncio.Task[None]] = {}

    def get_or_create(self, user_id: int) -> Amaya:
        amaya = self._instances.get(user_id)
        if amaya is None:
            amaya = Amaya(
                user_id=user_id,
                smart_llm_client=self.smart_llm_client,
                fast_llm_client=self.fast_llm_client,
            )
            self._instances[user_id] = amaya
            logger.info(f"创建用户独立 Amaya 实例: user_id={user_id}")
        return amaya

    def start_user_worker_if_needed(self, user_id: int) -> None:
        worker = self._workers.get(user_id)
        if worker is not None and not worker.done():
            return

        amaya = self.get_or_create(user_id)
        worker = asyncio.create_task(amaya.run_loop(), name=f"amaya-user-{user_id}")
        self._workers[user_id] = worker
        logger.info(f"已启动用户 worker: user_id={user_id}")

    def enqueue_incoming(self, msg: IncomingMessage) -> None:
        amaya = self.get_or_create(msg.user_id)
        self.start_user_worker_if_needed(msg.user_id)
        amaya.enqueue_task(AmayaTask(task_type="incoming_message", payload=msg))

    def enqueue_reminder(self, reminder: Reminder) -> None:
        amaya = self.get_or_create(reminder.user_id)
        self.start_user_worker_if_needed(reminder.user_id)
        amaya.enqueue_task(AmayaTask(task_type="reminder_triggered", payload=reminder))

    async def shutdown(self) -> None:
        if not self._workers:
            return

        logger.info("正在关闭 AmayaManager...")
        workers = list(self._workers.items())
        for _, task in workers:
            task.cancel()

        results = await asyncio.gather(*(task for _, task in workers), return_exceptions=True)
        for (user_id, _), result in zip(workers, results):
            if isinstance(result, Exception) and not isinstance(result, asyncio.CancelledError):
                logger.error(f"关闭用户 worker 时发生异常: user_id={user_id}, error={result}")

        self._workers.clear()
        self._instances.clear()
        logger.info("AmayaManager 已关闭")


_amaya_manager: AmayaManager | None = None


def configure_amaya_manager(manager: AmayaManager) -> None:
    global _amaya_manager
    _amaya_manager = manager


def _require_amaya_manager() -> AmayaManager:
    if _amaya_manager is None:
        raise RuntimeError("AmayaManager 尚未配置，请先调用 configure_amaya_manager()")
    return _amaya_manager


@bus.on(E.IO_SEND_MESSAGE)
async def save_message(msg: OutgoingMessage) -> None:
    await message_storage.create_message(msg.user_id, msg.channel_type, "amaya", msg.content)


@bus.on(E.IO_MESSAGE_RECEIVED)
async def handle_incoming_message(msg: IncomingMessage) -> None:
    logger.info(f"收到来自用户 {msg.user_id} 的消息，准备入队")
    await message_storage.create_message(msg.user_id, msg.channel_type, "user", msg.content)
    manager = _require_amaya_manager()
    manager.enqueue_incoming(msg)


@bus.on(E.REMINDER_TRIGGERED)
async def handle_reminder_triggered(reminder: Reminder):
    logger.info(f"触发 Reminder: id={reminder.reminder_id}, user_id={reminder.user_id}, title={reminder.title}")
    reminder.status = "sent"
    reminder.next_action_at_min_utc = None  # ToDo: 未来可能需要更复杂的状态机设计
    await reminder_storage.update_reminder(reminder)

    manager = _require_amaya_manager()
    manager.enqueue_reminder(reminder)



async def main_loop(shutdown_event: asyncio.Event = asyncio.Event()) -> None:
    """主异步事件循环"""
    _require_amaya_manager()
    logger.info("Orchestrator 主循环已启动")
    while not shutdown_event.is_set():
        await asyncio.sleep(1)

    logger.info("Orchestrator 已关闭")
