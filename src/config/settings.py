import os
from dotenv import load_dotenv
from config.logger import logger

load_dotenv()

# Telegram Bot
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if(TELEGRAM_BOT_TOKEN == None):
    logger.critical("TELEGRAM_BOT_TOKEN 未设置")
    exit(0)

ALLOWED_TELEGRAM_USER_IDS = [int(uid) for uid in os.getenv("ALLOWED_TELEGRAM_USER_IDS", "").split(",") if uid]
if(ALLOWED_TELEGRAM_USER_IDS == []):
    logger.warning("未设置 ALLOWED_TELEGRAM_USER_IDS, 所有用户均可访问 Bot")

ADMIN_TELEGRAM_USER_ID = int(os.getenv("ADMIN_TELEGRAM_USER_ID", "0"))


# LLM 设置
OPENAI_PRIMARY_API_KEY = os.getenv("OPENAI_PRIMARY_API_KEY")
if(OPENAI_PRIMARY_API_KEY == None):
    logger.critical("OPENAI_API_KEY 未设置")
    exit(0)

OPENAI_PRIMARY_BASE_URL = os.getenv("OPENAI_PRIMARY_BASE_URL", "https://api.openai.com/v1")
LLM_MAIN_MODEL = os.getenv("LLM_MAIN_MODEL", "gpt-5.2")
LLM_FAST_MODEL = os.getenv("LLM_FAST_MODEL", "gpt-5-nano")


# 用户设置
DEDEFAULT_TIMEZONE = os.getenv("DEDEFAULT_TIMEZONE", "UTC")

__all__ = [
    "TELEGRAM_BOT_TOKEN", "ALLOWED_TELEGRAM_USER_IDS", "ADMIN_TELEGRAM_USER_ID",
    "OPENAI_PRIMARY_API_KEY", "OPENAI_PRIMARY_BASE_URL", "LLM_MAIN_MODEL", "LLM_FAST_MODEL",
    "DEDEFAULT_TIMEZONE",
]
