from config.logger import setup_logging, logger
setup_logging(
    log_level="TRACE",
    log_file="logs/amaya.log",
    console_level="INFO",
)

import asyncio
import signal
from channels.telegram_polling import main as telegram_main
import core.orchestrator  # noqa: F401 用于注册事件处理程序
import storage.db_config

shutdown_event = asyncio.Event()

def signal_handler(sig, frame):
    """处理 SIGINT (Ctrl+C) 信号"""
    logger.info("收到中断信号,正在依次关闭组件...")
    shutdown_event.set()

async def main():
    # 注册信号处理器
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    await asyncio.gather(
        telegram_main(shutdown_event),
        core.orchestrator.main_loop(shutdown_event),
    )

if __name__ == "__main__":
    logger.info("启动 Amaya...")
    asyncio.run(main())
