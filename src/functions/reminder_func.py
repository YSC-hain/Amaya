from config.logger import logger
from config.settings import *
from events import bus, E
from functions.base import *
import storage.reminder as reminder_storage
import datetime
import pytz
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
                    "time": {
                        "type": "string",
                        "description": "The date and time of the reminder in 'YYYY-MM-DD HH:MM' format"
                    },
                    "prompt": {
                        "type": "string",
                        "description": "When a reminder is triggered, the conversation along with this prompt will be fed into Amaya to generate the most appropriate response for that moment. Ensure conciseness and accuracy."
                    }
                },
                "required": ["title", "time", "prompt"]
            }
        }

    async def execute(self, user_id: int, title: str, time: str, prompt: str):
        # 转换 datetime 到 UTC, 先使用配置中的时区推算(可能遗留问题)
        local_tz = pytz.timezone(DEDEFAULT_TIMEZONE)
        remind_at_local = local_tz.localize( datetime.datetime.strptime(time, '%Y-%m-%d %H:%M') )
        remind_at_utc = remind_at_local.astimezone(pytz.UTC).strftime('%Y-%m-%d %H:%M')

        reminder = await reminder_storage.create_reminder(
            user_id=user_id,
            title=title,
            remind_at_utc=remind_at_utc,
            prompt=prompt
        )
        return f"Reminder created with ID: {reminder.reminder_id}"

register_tool(CreateReminder())

__all__ = ["CreateReminder"]
