

import asyncio
import time
import threading
from typing import Callable, Awaitable, List, Dict, Any, Optional

import config
from modules.state_manager import AmayaState
from modules.world_simulator import World
from modules.physiological_model import Physiology
from modules.psychological_model import Psychology
from modules.memory_manager import Memory
from modules.scheduler import Scheduler
from modules.autonomous_agent import Agent
from modules.logger import event_logger, disable_console_logging
from modules.persistence_manager import PersistenceManager
from onebot_adapter import OneBotAdapter

from modules.perception import Perception_Layer

# 定义回调函数的类型签名
ReplyCallback = Callable[[Dict[str, Any]], Awaitable[None]]

# 使用一个字典来管理不同用户的 Amaya 实例
active_sessions: Dict[str, 'Amaya'] = {}

def get_or_create_session(user_id: str) -> 'Amaya':
    """
    获取或创建一个新的 Amaya 会话实例。
    """
    if user_id not in active_sessions:
        event_logger.log_event('SESSION_CREATE', {'user_id': user_id})
        print(f"为用户 {user_id} 创建新的会话...")
        amaya_instance = Amaya(user_id=user_id)
        amaya_instance.start() # 仅启动后台模拟线程
        active_sessions[user_id] = amaya_instance
        print(f"用户 {user_id} 的会话已启动。")
    return active_sessions[user_id]


class Amaya:
    def __init__(self, user_id: str):
        self.state = AmayaState(user_id)
        self.persistence_manager = PersistenceManager(user_id)
        self.world = World(self.state)
        self.physiology = Physiology(self.state)
        self.psychology = Psychology(self.state)
        self.memory = Memory(self.state, self.persistence_manager)
        self.scheduler = Scheduler(self.state)
        self.agent = Agent(self.state, self.memory)

        self.is_running = True
        self.last_checked_minute = -1
        self.tick_thread = threading.Thread(target=self._run_simulation_sync)

        # 用于追踪每个用户当前正在处理的输入任务
        self.active_user_tasks: Dict[str, asyncio.Task] = {}

    def _save_interaction_to_db(self, memories_to_save: List[Dict[str, Any]]):
        """将一组记忆和当前状态在一个事务中保存到数据库。"""
        try:
            with self.persistence_manager.transaction() as conn:
                cursor = conn.cursor()
                for mem in memories_to_save:
                    self.persistence_manager.save_memory(cursor, mem)
                self.persistence_manager.save_state(cursor, self.state)
            event_logger.log_event('INTERACTION_SAVED_TO_DB', {'user_id': self.state.user_id, 'memory_count': len(memories_to_save)})
        except Exception as e:
            event_logger.log_event('DB_ERROR', {'error': f"Failed to save interaction for user {self.state.user_id}: {e}"})

    def _save_state_to_db(self):
        """仅将当前状态在一个事务中保存到数据库。"""
        try:
            with self.persistence_manager.transaction() as conn:
                cursor = conn.cursor()
                self.persistence_manager.save_state(cursor, self.state)
            event_logger.log_event('STATE_SAVED_TO_DB', {'user_id': self.state.user_id})
        except Exception as e:
            event_logger.log_event('DB_ERROR', {'error': f"Failed to save state on exit for user {self.state.user_id}: {e}"})

    def _run_simulation_sync(self):
        """此函数在单独的线程中运行。与真实时间同步并检查是否有任务需要执行"""
        while self.is_running:
            self.world.tick()
            current_minute = self.state.current_time.minute
            self.physiology.tick(current_minute)

            if current_minute != self.last_checked_minute:
                current_hm = self.state.current_time.strftime("%H:%M")
                task = self.scheduler.get_task_for_time(current_hm)
                if task:
                    event_logger.log_event('SCHEDULED_TASK', {'task': task, 'user_id': self.state.user_id})
                    print(f"[系统内部事件] {self.state.current_time.strftime('%H:%M')} - {task}", flush=True)
                    internal_thought_mem = self.memory.add_memory(role="内部想法", content=task)
                    self._save_interaction_to_db([internal_thought_mem])

                self.last_checked_minute = current_minute

            time.sleep(1)

    async def process_user_input(self, user_input: str, reply_callback: ReplyCallback):
        """
        处理用户输入并生成回复的核心异步逻辑。
        此方法现在会管理任务中断。
        """
        if not user_input.strip():
            return

        # 如果该用户已有任务在运行，则取消它
        if self.state.user_id in self.active_user_tasks:
            self.active_user_tasks[self.state.user_id].cancel()
            event_logger.log_event('USER_INTERRUPTION', {'user_id': self.state.user_id})
            print("[系统消息] Amaya的思考被打断了...")

        # 创建并存储新任务
        task = asyncio.create_task(self._handle_input_lifecycle(user_input, reply_callback))
        self.active_user_tasks[self.state.user_id] = task

        try:
            await task
        except asyncio.CancelledError:
            # 任务被外部调用取消，是正常行为
            pass
        finally:
            # 清理已完成或被取消的任务
            if self.state.user_id in self.active_user_tasks and self.active_user_tasks[self.state.user_id].done():
                del self.active_user_tasks[self.state.user_id]

    async def _handle_input_lifecycle(self, user_input: str, reply_callback: ReplyCallback):
        """
        单个输入的完整生命周期，包括思考、回复和中断处理。
        """
        already_sent_messages = []
        memories_to_save = []

        try:
            event_logger.log_event('USER_INPUT', {'content': user_input, 'user_id': self.state.user_id})
            user_input_mem = self.memory.add_memory(role="用户", content=user_input)
            memories_to_save.append(user_input_mem)

            # 检查并传递中断和模式上下文
            interruption_ctx = self.state.interruption_context
            interaction_mode = self.state.interaction_mode
            # 使用后立即清除，确保它只被用一次
            self.state.interruption_context = None

            # 调用LLM生成响应
            response_messages = await asyncio.to_thread(
                self.agent.generate_response,
                user_input_mem['content'],
                interruption_ctx,
                interaction_mode
            )

            if response_messages:
                for i, message in enumerate(response_messages):
                    if i == 0:
                        delay = max(message.get("delay seconds", 5) - 5, 0)  # 解决首次消息回复耗时过长的问题
                    else:
                        delay = message.get("delay seconds", 1)
                    await asyncio.sleep(delay)

                    content = message.get("content", "...")
                    # 1. 发送消息，这是IO操作，可能被打断
                    await reply_callback(message)

                    # 2. 消息发送成功后，立即同步记录所有相关信息
                    # 这是核心修复：确保只有真正发送了的消息才会被记录
                    event_logger.log_event('AMAYA_RESPONSE', {'content': content, 'delay': delay, 'user_id': self.state.user_id})
                    amaya_response_mem = self.memory.add_memory(role="Amaya", content=content)
                    memories_to_save.append(amaya_response_mem)
                    already_sent_messages.append(content)
            else:
                event_logger.log_event('AMAYA_NO_RESPONSE', {'reason': 'LLM decided not to respond.', 'user_id': self.state.user_id})

            # 异步保存交互到数据库
            await asyncio.to_thread(self._save_interaction_to_db, memories_to_save)

        except asyncio.CancelledError:
            print("[系统消息] 任务被取消，正在保存中断上下文...")
            # 如果在生成响应的过程中被取消
            if 'response_messages' in locals() and response_messages:
                # 找出还没来得及发送的消息
                unsent_messages = response_messages[len(already_sent_messages):]
                if unsent_messages:
                    self.state.interruption_context = {
                        'already_sent': already_sent_messages,
                        'unsent_message': unsent_messages[0]['content'] # 只保存第一条未发送的
                    }
                    event_logger.log_event('INTERRUPTION_CONTEXT_SAVED', {'context': self.state.interruption_context, 'user_id': self.state.user_id})

            # 即使被中断，也要保存用户输入
            await asyncio.to_thread(self._save_interaction_to_db, memories_to_save)
            # 重新抛出异常，以便上层处理
            raise

    def start(self):
        """同步方法，用于加载数据和启动后台模拟线程。"""
        is_existing_user = self.persistence_manager.load_state(self.state)
        self.persistence_manager.load_full_memory_archive(self.state)
        self.memory.rebuild_short_term_from_full_archive()

        self.tick_thread.start()
        event_logger.log_event('SYSTEM_START', {'user_id': self.state.user_id})

        if is_existing_user:
            print(f"欢迎回来, {self.state.user_id}！Amaya 已恢复上次的状态。")
        else:
            print(f"你好, {self.state.user_id}！这是一个新的开始。")

    def stop(self):
        """同步方法，用于停止后台线程和保存最终状态。"""
        self.is_running = False
        if self.tick_thread.is_alive():
            self.tick_thread.join()

        # 取消所有正在进行的任务
        for task in self.active_user_tasks.values():
            task.cancel()

        self._save_state_to_db()
        self.persistence_manager.close()

        event_logger.log_event('SYSTEM_SHUTDOWN', {'user_id': self.state.user_id})
        print(f"用户 {self.state.user_id} 的会话已结束，Amaya 已关闭。")

    def print_status(self):
        event_logger.log_event('STATUS_CHECK', {'user_id': self.state.user_id})
        print(f"--- 用户: {self.state.user_id} 的 Amaya 当前状态 ---")
        print(f"时间: {self.state.current_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"精力: {int(self.state.energy)}/100")
        print(f"情绪: {self.state.mood}, 好感度: {self.state.favorability}")
        print(f"短期记忆条数: {len(self.state.short_term_memory)}")
        print(f"长期记忆存档条数: {len(self.state.full_memory_archive)}")
        print(f"当前行动: {self.state.current_action}")
        print(f"交互模式: {self.state.interaction_mode}")
        print("------------------------------")


# -- 应用关闭事件 --
def shutdown_sessions():
    print("程序正在关闭...")
    for user_id, amaya_instance in active_sessions.items():
        print(f"正在为用户 {user_id} 保存状态并关闭会话...")
        amaya_instance.stop()
    print("所有会话已关闭。")


class OneBotMessageHandler:
    """处理 OneBot 消息的类，避免循环引用问题"""
    def __init__(self):
        self.onebot_adapter = None
        self.perception = Perception_Layer()
    
    def set_adapter(self, adapter):
        """设置适配器实例"""
        self.onebot_adapter = adapter
    
    async def handle_message(self, event: Dict[str, Any]):
        """
        处理从 OneBot 适配器接收到的消息事件。
        """
        if event.get("post_type") == "message" and event.get("message_type") == "private":
            user_id = str(event.get("user_id"))
            message_text = self.perception.format_message(event.get('message'))

            amaya = get_or_create_session(user_id)

            # 定义一个 OneBot 特定的回调函数
            async def onebot_reply_callback(response_message: Dict[str, Any]):
                content = response_message.get("content", "...")
                if self.onebot_adapter:
                    await self.onebot_adapter.send_api_call(
                        action="send_private_msg",
                        params={"user_id": int(user_id), "message": content}
                    )

            # 调用 Amaya 的核心处理逻辑，并传入 OneBot 的回调
            await amaya.process_user_input(message_text, onebot_reply_callback)


async def main():
    """
    主函数，负责启动 OneBot 适配器和 Amaya 的自主行动循环。
    """
    print("========================================")
    print("  Amaya - 主程序启动  ")
    print("========================================")

    # 禁用控制台日志以保持界面清洁，日志将仅写入文件
    disable_console_logging()
    print("[注意] 控制台日志已禁用，日志将仅写入 amaya_log.jsonl 文件。")

    # 创建消息处理器实例
    message_handler = OneBotMessageHandler()
    
    # 初始化 OneBot 适配器
    onebot_adapter = OneBotAdapter(message_handler=message_handler.handle_message)
    
    # 设置适配器实例，解决循环引用问题
    message_handler.set_adapter(onebot_adapter)

    # 启动 OneBot 适配器任务
    onebot_task = asyncio.create_task(onebot_adapter.run())

    # --- Amaya 自主行动主循环 (未来实现) ---
    # 这里可以添加 Amaya 的自主行动逻辑，例如定时任务、环境感知等
    # 目前只是一个简单的循环，防止程序退出
    try:
        while True:
            # print("[主循环] Amaya 正在自主行动...") # 避免频繁打印
            await asyncio.sleep(60) # 每分钟检查一次，或根据需要调整

    except asyncio.CancelledError:
        print("主循环被取消。" )
    finally:
        onebot_task.cancel()
        await onebot_task # 等待 OneBot 任务完成取消


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n检测到手动中断，正在关闭...")
    finally:
        shutdown_sessions()
        print("程序已完全关闭。")
