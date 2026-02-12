"""工作记忆操作函数 v0.1

工作记忆的设计原则是简单可靠。在此划分为两层的架构：
1. 记忆组: 类似文件夹的结构，方便 LLM 组织记忆；
2. 记忆点：具体的记忆信息，字典结构，键代表“记忆锚点”，值代表“记忆内容”
"""

from config.logger import logger
from functions.base import *
import storage.work_memory as work_memory_storage

__all__ = ["CreateMemoryGroup", "CreateMemoryPoint"]

class CreateMemoryGroup(BaseFunction):
    @property
    def tool_schema(self) -> dict:
        return {
            "type": "function",
            "name": "create_memory_group",
            "description": "Create a new work memory group to organize memory points.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "The title of the memory group. Keep it as short as possible. Do not use existing titles."
                    }
                },
                "required": ["title"]
            }
        }

    async def execute(self, user_id: int, title: str) -> str:
        res = await work_memory_storage.create_memory_group(user_id, title)
        if res == -1:
            return f"Creation failed. Memory group with title '{title}' already exists."
        else:
            return f"Memory group created with title: '{title}'"

register_tool(CreateMemoryGroup())


class CreateMemoryPoint(BaseFunction):
    @property
    def tool_schema(self) -> dict:
        return {
            "type": "function",
            "name": "create_memory_point",
            "description": "Create a new memory point in a specified memory group.",
            "parameters": {
                "type": "object",
                "properties": {
                    "memory_group_title": {
                        "type": "string",
                        "description": "The title of the memory group where the memory point will be added."
                    },
                    "anchor": {
                        "type": "string",
                        "description": "The anchor (key) of memory point."
                    },
                    "content": {
                        "type": "string",
                        "description": "The content (value) of memory point."
                    },
                    "memory_type": {
                        "type": "string",
                        "description": "The type of memory point, must be within ['fact', 'emotion', 'work']."
                    },
                    "weight": {
                        "type": "number",
                        "description": "Memory Strength, ranging from 0 to 1. Default is `1.0`.",
                        "default": 1.0
                    }
                },
                "required": ["memory_group_title", "anchor", "content", "memory_type"]
            }
        }

    async def execute(self, user_id: int, memory_group_title: str, anchor: str, content: str, memory_type: str, weight: float = 1.0) -> str:
        res = await work_memory_storage.create_memory_point(user_id, memory_group_title, anchor, content, memory_type, weight)
        if res == -1:
            return f"Creation failed. Memory group with title '{memory_group_title}' does not exist."
        else:
            return f"Memory point created with anchor: '{anchor}' in group: '{memory_group_title}'"

register_tool(CreateMemoryPoint())


class EditMemoryPointContent(BaseFunction):
    @property
    def tool_schema(self) -> dict:
        return {
            "type": "function",
            "name": "edit_memory_point_content",
            "description": "Edit the content of an existing memory point. Only useful for work memory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "memory_point_id": {
                        "type": "integer",
                        "description": "The ID of the memory point to be edited."
                    },
                    "new_content": {
                        "type": "string",
                        "description": "The new content for the memory point."
                    }
                },
                "required": ["memory_point_id", "new_content"]
            }
        }

    async def execute(self, user_id: int, memory_point_id: int, new_content: str) -> str:
        res = await work_memory_storage.edit_memory_point_content_by_id(user_id, memory_point_id, new_content)
        if res is False:
            return f"Edit failed. Memory point with ID '{memory_point_id}' does not exist."
        else:
            return f"Memory point with ID '{memory_point_id}' has been updated."

register_tool(EditMemoryPointContent())
