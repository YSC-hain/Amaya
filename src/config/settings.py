import os
from dotenv import load_dotenv
from logger import logger
load_dotenv()

__all__ = [
    "ENABLE_TELEGRAM_BOT_POLLING",
    "TELEGRAM_BOT_TOKEN", "PRIMARY_TELEGRAM_USER_ID",
    "ENABLE_QQ_NAPCAT", "QQ_NAPCAT_WS_PATH", "QQ_NAPCAT_WS_TOKEN",
    "PRIMARY_QQ_USER_ID", "QQ_NAPCAT_ENABLE_GROUP", "QQ_NAPCAT_SEND_TIMEOUT_SECONDS",
    "LLM_PROVIDER", "OPENAI_PRIMARY_API_KEY", "OPENAI_PRIMARY_BASE_URL", "GEMINI_API_KEY", "GEMINI_BASE_URL",
    "LLM_MAIN_MODEL", "LLM_FAST_MODEL",
    "USER_NAME", "USER_TIMEZONE", "USER_EMAIL", "PRIMARY_CONTACT_METHOD",
    "ADMIN_HTTP_HOST", "ADMIN_HTTP_PORT", "ADMIN_AUTH_TOKEN",
    "WEBHOOK_SHARED_SECRET", "ADMIN_LOG_FILE",
]


def _parse_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on", "y")


# 动态加载的环境变量
# 用户个人信息
USER_NAME = os.getenv("USER_NAME", "User")
USER_TIMEZONE = os.getenv("USER_TIMEZONE", "Asia/Shanghai")
USER_EMAIL = os.getenv("USER_EMAIL", "")

# 主联系方式: "telegram" 或 "qq"
PRIMARY_CONTACT_METHOD = os.getenv("PRIMARY_CONTACT_METHOD", "telegram").strip().lower()
if PRIMARY_CONTACT_METHOD not in ("telegram", "qq"):
    logger.critical(f"PRIMARY_CONTACT_METHOD 非法: {PRIMARY_CONTACT_METHOD}, 仅支持 telegram 或 qq")
    exit(0)

# Telegram Bot
ENABLE_TELEGRAM_BOT_POLLING = _parse_bool("ENABLE_TELEGRAM_BOT_POLLING", True)
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
if ENABLE_TELEGRAM_BOT_POLLING and TELEGRAM_BOT_TOKEN == "":
    logger.critical("已启用 Telegram Bot Polling, 但 TELEGRAM_BOT_TOKEN 未设置")
    exit(0)

PRIMARY_TELEGRAM_USER_ID = int(os.getenv("PRIMARY_TELEGRAM_USER_ID", "0"))
if ENABLE_TELEGRAM_BOT_POLLING and PRIMARY_TELEGRAM_USER_ID == 0:
    logger.warning("未设置 PRIMARY_TELEGRAM_USER_ID")


# QQ / NapCat
ENABLE_QQ_NAPCAT = _parse_bool("ENABLE_QQ_NAPCAT", False)
QQ_NAPCAT_WS_PATH = os.getenv("QQ_NAPCAT_WS_PATH", "/channels/qq/onebot/ws")
QQ_NAPCAT_WS_TOKEN = os.getenv("QQ_NAPCAT_WS_TOKEN", "")
PRIMARY_QQ_USER_ID = int(os.getenv("PRIMARY_QQ_USER_ID", "0"))
QQ_NAPCAT_ENABLE_GROUP = _parse_bool("QQ_NAPCAT_ENABLE_GROUP", False)
if ENABLE_QQ_NAPCAT and PRIMARY_QQ_USER_ID == 0:
    logger.warning("未设置 PRIMARY_QQ_USER_ID")

try:
    QQ_NAPCAT_SEND_TIMEOUT_SECONDS = float(os.getenv("QQ_NAPCAT_SEND_TIMEOUT_SECONDS", "10"))
except ValueError:
    QQ_NAPCAT_SEND_TIMEOUT_SECONDS = 10.0
    logger.warning("QQ_NAPCAT_SEND_TIMEOUT_SECONDS 非法, 已回退到 10 秒")


# LLM 设置
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai").strip().lower()
if LLM_PROVIDER not in ("openai", "gemini"):
    logger.critical(f"LLM_PROVIDER 非法: {LLM_PROVIDER}, 仅支持 openai 或 gemini")
    exit(0)

OPENAI_PRIMARY_API_KEY = os.getenv("OPENAI_PRIMARY_API_KEY")
OPENAI_PRIMARY_BASE_URL = os.getenv("OPENAI_PRIMARY_BASE_URL", "https://api.openai.com/v1")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_BASE_URL = os.getenv("GEMINI_BASE_URL")

if LLM_PROVIDER == "openai" and OPENAI_PRIMARY_API_KEY is None:
    logger.critical("当前 LLM_PROVIDER=openai, 但 OPENAI_PRIMARY_API_KEY 未设置")
    exit(0)

if LLM_PROVIDER == "gemini" and GEMINI_API_KEY is None:
    logger.critical("当前 LLM_PROVIDER=gemini, 但 GEMINI_API_KEY 未设置")
    exit(0)

LLM_MAIN_MODEL = os.getenv("LLM_MAIN_MODEL", "gpt-5.2")
LLM_FAST_MODEL = os.getenv("LLM_FAST_MODEL", "gpt-5-nano")


# Admin API/Web
ADMIN_HTTP_HOST = os.getenv("ADMIN_HTTP_HOST", "127.0.0.1")
ADMIN_HTTP_PORT = int(os.getenv("ADMIN_HTTP_PORT", "18080"))
ADMIN_AUTH_TOKEN = os.getenv("ADMIN_AUTH_TOKEN", "")

WEBHOOK_SHARED_SECRET = os.getenv("WEBHOOK_SHARED_SECRET", "")
ADMIN_LOG_FILE = os.getenv("ADMIN_LOG_FILE", "logs/amaya.log")
