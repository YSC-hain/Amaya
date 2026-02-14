from logger import setup_logging, logger
from config.settings import *
setup_logging(
    log_level="TRACE",
    log_file=ADMIN_LOG_FILE,
    console_level="INFO",
)

import asyncio
import os
import signal
import sys

from config.prompts import CORE_SYSTEM_PROMPT
from datamodel import *
from channels.telegram_polling import main as telegram_main
from channels.qq_onebot_ws import main as qq_main
from admin.http_server import main_loop as admin_http_main
import core.orchestrator as orchestrator
from core.amaya import Amaya, configure_amaya
import world.reminder
import storage.db_config as db_config
from llm.base import LLMClient

shutdown_event = asyncio.Event()
restart_event = asyncio.Event()

def signal_handler(sig, frame):
    """处理 SIGINT (Ctrl+C) 信号"""
    logger.info("收到中断信号,正在依次关闭组件...")
    shutdown_event.set()

def _create_llm_clients() -> tuple[LLMClient, LLMClient]:
    """临时函数，根据配置创建 LLM 客户端实例"""
    if LLM_PROVIDER == "openai":
        from llm.openai_client import OpenAIClient

        smart_llm_client = OpenAIClient(model=LLM_MAIN_MODEL, inst=CORE_SYSTEM_PROMPT)
        fast_llm_client = OpenAIClient(model=LLM_FAST_MODEL, inst=CORE_SYSTEM_PROMPT)
        return smart_llm_client, fast_llm_client

    if LLM_PROVIDER == "gemini":
        from llm.gemini_client import GeminiClient

        smart_llm_client = GeminiClient(model=LLM_MAIN_MODEL, inst=CORE_SYSTEM_PROMPT)
        fast_llm_client = GeminiClient(model=LLM_FAST_MODEL, inst=CORE_SYSTEM_PROMPT)
        return smart_llm_client, fast_llm_client

    raise ValueError(f"不支持的 LLM_PROVIDER: {LLM_PROVIDER}")

def _get_primary_channel() -> tuple[ChannelType, dict | None]:
    """获取主联系方式对应的通道"""
    if PRIMARY_CONTACT_METHOD == "telegram":
        return ChannelType.TELEGRAM_BOT_POLLING, None
    elif PRIMARY_CONTACT_METHOD == "qq":
        return ChannelType.QQ_NAPCAT_ONEBOT_V11, None
    else:
        raise ValueError(f"不支持的主联系方式: {PRIMARY_CONTACT_METHOD}")


async def main():
    # 注册信号处理器
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    smart_llm_client, fast_llm_client = _create_llm_clients()
    amaya = Amaya(
        smart_llm_client=smart_llm_client,
        fast_llm_client=fast_llm_client,
        channel=_get_primary_channel(),
    )
    configure_amaya(amaya)

    await db_config.init_db("data/amaya.db")

    try:
        tasks = [
            world.reminder.main_loop(shutdown_event),
            amaya.run_loop(shutdown_event),
            admin_http_main(shutdown_event, restart_event),
        ]

        if ENABLE_TELEGRAM_BOT_POLLING:
            tasks.append(telegram_main(shutdown_event))
        else:
            logger.warning("Telegram Bot Polling 已禁用")

        if ENABLE_QQ_NAPCAT:
            tasks.append(qq_main(shutdown_event))
        else:
            logger.warning("NapCatQQ 通道已禁用")

        await asyncio.gather(*tasks)
    finally:
        logger.info("关闭 Amaya...")

        logger.info("关闭数据库连接...")
        if db_config.conn is not None:
            await db_config.conn.close()
            db_config.conn = None
        if restart_event.is_set():
            logger.warning("检测到重启信号，正在重新拉起进程...")
            try:
                os.execv(sys.executable, [sys.executable, *sys.argv])
            except Exception as e:
                logger.error(f"重启失败: {e}", exc_info=e)
        logger.info("Amaya 已关闭")


if __name__ == "__main__":
    logger.info("启动 Amaya...")
    asyncio.run(main())
