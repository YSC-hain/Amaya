from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from enum import Enum
from datetime import datetime

class ChannelType(str, Enum):
    TELEGRAM_BOT_POLLING = "telegram_bot_polling"
    #TELEGRAM_BOT_WEBHOOK = "telegram_bot_webhook"

@dataclass
class IncomingMessage:
    channel_type: ChannelType
    user_id: int  # 注意，该user_id是平台内部的user_id
    content: str
    attachments: Optional[List[Dict[str, str]]] = None  # {mime_type: str, cache_name: str}
    channel_context: Any = None  # 平台上下文对象
    metadata: Optional[Dict[str, Any]] = None  # 平台特定元数据
    timestamp: Optional[datetime] = None

@dataclass
class OutgoingMessage:
    channel_type: ChannelType
    user_id: int  # 注意，该user_id是平台内部的user_id
    content: str
    attachments: Optional[List[Dict[str, str]]] = None  # {mime_type: str, cache_name: str}
    channel_context: Any = None  # 平台上下文对象
    metadata: Optional[Dict[str, Any]] = None  # 平台特定元数据
