from config.logger import logger
from config.settings import *
from events import bus, E
from channels.base import ChannelType, IncomingMessage, OutgoingMessage
from llm.openai_client import OpenAIClient
from config.prompts import *
from typing import List, Dict
import asyncio
import time

class Amaya:
    """Amaya核心类"""

    def __init__(self) -> None:
        self.smart_llm_client = OpenAIClient(model=LLM_MAIN_MODEL, inst=CORE_SYSTEM_PROMPT) # ToDo
        self.fast_llm_client = OpenAIClient(model=LLM_FAST_MODEL, inst=CORE_SYSTEM_PROMPT)
    
    async def process_msg(self, msg: IncomingMessage) -> None:
        llm_context: List[Dict[str, str]] = [
            {
                "role": "user",
                "content": msg.content,
            }
        ]
        start_time = time.perf_counter()
        res = await amaya.fast_llm_client.generate_response(llm_context)
        end_time = time.perf_counter()
        logger.info(f"LLM响应时间: {end_time - start_time:.2f} 秒")

        return res

amaya = Amaya()

@bus.on(E.IO_MESSAGE_RECEIVED)
async def handle_incoming_message(msg: IncomingMessage) -> None:
    logger.info(f"处理来自用户 {msg.user_id} 的消息: {msg.content}")

    res = await amaya.process_msg(msg)
    
    bus.emit(E.IO_SEND_MESSAGE, OutgoingMessage(
        channel_type = msg.channel_type,
        user_id = msg.user_id,
        content = f"{res}",
        channel_context = msg.channel_context,
    ))


async def main_loop(shutdown_event: asyncio.Event = asyncio.Event()) -> None:
    """主异步事件循环"""
    logger.info("Orchestrator 主循环已启动")
    while not shutdown_event.is_set():
        logger.trace("Amaya Tick")
        await asyncio.sleep(10)
    
    logger.info("关闭 Orchestrator")
