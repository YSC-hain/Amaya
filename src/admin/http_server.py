from __future__ import annotations

import asyncio
import time

import uvicorn
from config.settings import ADMIN_HTTP_HOST, ADMIN_HTTP_PORT
from logger import logger

from .app import create_app
from .schemas import RuntimeControl


async def _wait_shutdown_signal(shutdown_event: asyncio.Event, server: uvicorn.Server) -> None:
    await shutdown_event.wait()
    server.should_exit = True


async def main_loop(
    shutdown_event: asyncio.Event,
    restart_event: asyncio.Event,
) -> None:
    control = RuntimeControl(
        shutdown_event=shutdown_event,
        restart_event=restart_event,
        started_at=time.time(),
    )
    app = create_app(control)

    config = uvicorn.Config(
        app,
        host=ADMIN_HTTP_HOST,
        port=ADMIN_HTTP_PORT,
        log_level="info",
        access_log=False,
    )
    server = uvicorn.Server(config)
    # 嵌入到主进程时，统一由 main.py 处理系统信号。
    server.install_signal_handlers = lambda: None

    watcher = asyncio.create_task(_wait_shutdown_signal(shutdown_event, server))
    logger.info(f"Admin HTTP 服务准备启动: http://{ADMIN_HTTP_HOST}:{ADMIN_HTTP_PORT}")
    try:
        await server.serve()
    finally:
        watcher.cancel()
        try:
            await watcher
        except asyncio.CancelledError:
            pass
        logger.info("Admin HTTP 服务已关闭")
