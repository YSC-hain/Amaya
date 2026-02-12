"""事件总线模块，定义了事件总线类 Bus 及事件名集合 E
事件分为两种：
1. 普通事件：允许多个处理器注册;
2. 独占事件：仅允许一个处理器注册，尝试重复注册会引发运行时错误(未实现);
(暂时不使用以上逻辑，仅作预留)
"""

from __future__ import annotations
from pyee.asyncio import AsyncIOEventEmitter
from typing import Awaitable, Callable, Dict, Set
from functools import wraps

from logger import logger

AsyncHandler = Callable[..., Awaitable[None]]

# 事件名集中定义
class E:
    # 普通事件
    IO_MESSAGE_RECEIVED = "io.message_received"
    IO_SEND_MESSAGE = "io.send_message"
    REMINDER_CREATED = "reminder.created"
    REMINDER_TRIGGERED = "reminder.triggered"
    REMINDER_SENT = "reminder.sent"

EXCLUSIVE_EVENTS = {}


class Bus(AsyncIOEventEmitter):
    def __init__(self) -> None:
        super().__init__()
        self._exclusive: Set[str] = set()

    def on(self, event: str) -> Callable[[AsyncHandler], AsyncHandler]:
        """注册事件处理器装饰器"""
        def decorator(handler: AsyncHandler) -> AsyncHandler:
            # 检查独占事件
            if event in EXCLUSIVE_EVENTS:
                if event in self._exclusive:
                    raise RuntimeError(f"独占事件的唯一处理器已注册: {event}")
                self._exclusive.add(event)
            
            # 注册到父类
            logger.debug(f"注册事件处理器: {event} -> {handler.__name__}")
            super(Bus, self).on(event, handler)
            return handler
        
        return decorator


bus = Bus()

__all__ = ["bus", "E"]