from config.logger import logger
from functions.base import *
import asyncio
from typing import Callable, Dict

class CreateReminder(BaseFunction):
    @property
    def tool_schema(self) -> dict:
        return {
            "type": "function",
            "name": "create_reminder",
            "description": "Create a new reminder",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "The title of the reminder"
                    },
                    "datetime": {
                        "type": "string",
                        "description": "The date and time of the reminder in YYYY-MM-DD HH:MM format"
                    },
                    "prompt": {
                        "type": "string",
                        "description": "When a reminder is triggered, the conversation along with this prompt will be fed into the LLM to generate the most appropriate response for that moment."
                    }
                },
                "required": ["title", "datetime", "prompt"]
            }
        }

    async def execute(self, title: str, datetime: str, prompt: str):
        # ToDo: 添加实际的提醒创建逻辑
        reminder = {
            "title": title,
            "datetime": datetime,
            "prompt": prompt
        }
        logger.info(f"[Mock] 创建提醒: {reminder}")
        # 模拟异步操作
        await asyncio.sleep(0.1)
        return f"提醒已创建: {reminder}"

register_tool(CreateReminder())

__all__ = ["CreateReminder"]
