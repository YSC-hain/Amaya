from config.logger import setup_logging, logger
setup_logging(
    log_level="TRACE",
    log_file="logs/amaya.log",
    console_level="INFO",
)

import asyncio
import signal

from channels.telegram_polling import main as telegram_main
import core.orchestrator
import world.reminder
import storage.db_config as db_config

shutdown_event = asyncio.Event()

def signal_handler(sig, frame):
    """处理 SIGINT (Ctrl+C) 信号"""
    logger.info("收到中断信号,正在依次关闭组件...")
    shutdown_event.set()

async def main():
    # 注册信号处理器
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    await db_config.init_db("data/amaya.db")

    try:
        await asyncio.gather(
            telegram_main(shutdown_event),
            core.orchestrator.main_loop(shutdown_event),
            world.reminder.main_loop(shutdown_event),
        )
    finally:
        logger.info("关闭数据库连接...")
        if db_config.conn is not None:
            await db_config.conn.close()
        logger.info("Amaya 已关闭")


if __name__ == "__main__":
    logger.info("启动 Amaya...")
    asyncio.run(main())
