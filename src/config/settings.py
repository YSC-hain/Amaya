import os
from dotenv import load_dotenv
from logger import logger

load_dotenv()


def _parse_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on", "y")


def _parse_int_list(name: str) -> list[int]:
    values: list[int] = []
    raw = os.getenv(name, "")
    for item in raw.split(","):
        item = item.strip()
        if not item:
            continue
        try:
            values.append(int(item))
        except ValueError:
            logger.warning(f"{name} 包含非整数值: {item}, 已忽略")
    return values


# Telegram Bot
ENABLE_TELEGRAM_BOT_POLLING = _parse_bool("ENABLE_TELEGRAM_BOT_POLLING", True)
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
if ENABLE_TELEGRAM_BOT_POLLING and TELEGRAM_BOT_TOKEN == "":
    logger.critical("已启用 Telegram Bot Polling, 但 TELEGRAM_BOT_TOKEN 未设置")
    exit(0)

ALLOWED_TELEGRAM_USER_IDS = _parse_int_list("ALLOWED_TELEGRAM_USER_IDS")
if ENABLE_TELEGRAM_BOT_POLLING and ALLOWED_TELEGRAM_USER_IDS == []:
    logger.warning("未设置 ALLOWED_TELEGRAM_USER_IDS, 所有用户均可访问 Bot")

ADMIN_TELEGRAM_USER_ID = int(os.getenv("ADMIN_TELEGRAM_USER_ID", "0"))


# QQ / NapCat
ENABLE_QQ_NAPCAT = _parse_bool("ENABLE_QQ_NAPCAT", False)
QQ_NAPCAT_WS_PATH = os.getenv("QQ_NAPCAT_WS_PATH", "/channels/qq/onebot/ws")
QQ_NAPCAT_WS_TOKEN = os.getenv("QQ_NAPCAT_WS_TOKEN", "")
ALLOWED_QQ_USER_IDS = _parse_int_list("ALLOWED_QQ_USER_IDS")
QQ_NAPCAT_ENABLE_GROUP = _parse_bool("QQ_NAPCAT_ENABLE_GROUP", False)
if ENABLE_QQ_NAPCAT and ALLOWED_QQ_USER_IDS == []:
    logger.warning("未设置 ALLOWED_QQ_USER_IDS, 所有 QQ 用户均可访问 Bot")

try:
    QQ_NAPCAT_SEND_TIMEOUT_SECONDS = float(os.getenv("QQ_NAPCAT_SEND_TIMEOUT_SECONDS", "10"))
except ValueError:
    QQ_NAPCAT_SEND_TIMEOUT_SECONDS = 10.0
    logger.warning("QQ_NAPCAT_SEND_TIMEOUT_SECONDS 非法, 已回退到 10 秒")


# LLM 设置
OPENAI_PRIMARY_API_KEY = os.getenv("OPENAI_PRIMARY_API_KEY")
if OPENAI_PRIMARY_API_KEY == None:
    logger.critical("OPENAI_API_KEY 未设置")
    exit(0)

OPENAI_PRIMARY_BASE_URL = os.getenv("OPENAI_PRIMARY_BASE_URL", "https://api.openai.com/v1")
LLM_MAIN_MODEL = os.getenv("LLM_MAIN_MODEL", "gpt-5.2")
LLM_FAST_MODEL = os.getenv("LLM_FAST_MODEL", "gpt-5-nano")


# 用户设置
DEDEFAULT_TIMEZONE = os.getenv("DEDEFAULT_TIMEZONE", "UTC")

# Admin API/Web
ADMIN_HTTP_HOST = os.getenv("ADMIN_HTTP_HOST", "127.0.0.1")
ADMIN_HTTP_PORT = int(os.getenv("ADMIN_HTTP_PORT", "18080"))
ADMIN_AUTH_TOKEN = os.getenv("ADMIN_AUTH_TOKEN", "")

WEBHOOK_SHARED_SECRET = os.getenv("WEBHOOK_SHARED_SECRET", "")
ADMIN_LOG_FILE = os.getenv("ADMIN_LOG_FILE", "logs/amaya.log")

__all__ = [
    "ENABLE_TELEGRAM_BOT_POLLING",
    "TELEGRAM_BOT_TOKEN", "ALLOWED_TELEGRAM_USER_IDS", "ADMIN_TELEGRAM_USER_ID",
    "ENABLE_QQ_NAPCAT", "QQ_NAPCAT_WS_PATH", "QQ_NAPCAT_WS_TOKEN",
    "ALLOWED_QQ_USER_IDS", "QQ_NAPCAT_ENABLE_GROUP", "QQ_NAPCAT_SEND_TIMEOUT_SECONDS",
    "OPENAI_PRIMARY_API_KEY", "OPENAI_PRIMARY_BASE_URL", "LLM_MAIN_MODEL", "LLM_FAST_MODEL",
    "DEDEFAULT_TIMEZONE",
    "ADMIN_HTTP_HOST", "ADMIN_HTTP_PORT", "ADMIN_AUTH_TOKEN",
    "WEBHOOK_SHARED_SECRET", "ADMIN_LOG_FILE",
]
