from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from enum import Enum
from datetime import datetime

__all__ = [
    "Reminder",
    "ChannelType", "IncomingMessage", "OutgoingMessage",
    "FunctionCall",
    "UserInfo",
]

# ----------------- Reminder 数据模型 ----------------
@dataclass
class Reminder:
    reminder_id: int
    user_id: int
    title: str
    remind_at_min_utc: str  # 格式: "YYYY-MM-DD HH:MM"
    prompt: str
    status: str = "pending"  # 'pending', 'sent', 'acked', 'snoozed', 'escalated', 'ignored', 'cancelled'
    next_action_at_min_utc: str = None  # 格式: "YYYY-MM-DD HH:MM"


# ----------------- Channel 数据模型 ----------------
class ChannelType(str, Enum):
    TELEGRAM_BOT_POLLING = "telegram_bot_polling"
    QQ_NAPCAT_ONEBOT_V11 = "qq_napcat_onebot_v11"
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


# ----------------- Function 数据模型 ----------------
@dataclass
class FunctionCall:
    name: str
    arguments: Dict[str, Any]  # 要求附加 user_id 参数


# ----------------- User 数据模型 ----------------
@dataclass
class UserInfo:
    user_id: int
    user_name: Optional[str] = None
    timezone: Optional[str] = None  # IANA时区字符串，例如 "Asia/Shanghai"
    email: Optional[str] = None
    telegram_user_id: Optional[int] = None
    qq_user_id: Optional[int] = None
