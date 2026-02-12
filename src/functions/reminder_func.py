from logger import logger
from config.settings import *
from events import bus, E
from functions.base import *
import storage.reminder as reminder_storage
import storage.user as user_storage
from utils import *

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
                        "description": "The title of the reminder, such as '微积分作业'"
                    },
                    "time": {
                        "type": "string",
                        "description": "The date and time of the reminder in 'YYYY-MM-DD HH:MM' format"
                    },
                    "prompt": {
                        "type": "string",
                        "description": "When a reminder is triggered, the conversation along with this prompt will be fed into Amaya to generate the most appropriate response for that moment. Ensure conciseness and accuracy. Such as '提醒用户完成微积分作业'"  # 在提示词中融入username以实现更好的效果
                    }
                },
                "required": ["title", "time", "prompt"]
            }
        }

    async def execute(self, user_id: int, title: str, time: str, prompt: str):
        user_info = await user_storage.get_user_by_id(user_id)
        remind_at_min_utc = user_local_min_to_utc_min_str(time, user_info.timezone)

        reminder = await reminder_storage.create_reminder(
            user_id=user_id,
            title=title,
            remind_at_min_utc=remind_at_min_utc,
            prompt=prompt
        )
        return f"Reminder created with ID: {reminder.reminder_id}"

register_tool(CreateReminder())

__all__ = ["CreateReminder"]
