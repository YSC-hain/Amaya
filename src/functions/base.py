from abc import ABC, abstractmethod
from dataclasses import dataclass
from config.logger import logger
from typing import Any, Dict, List, Optional

class BaseFunction(ABC):
    @property
    @abstractmethod
    def tool_schema(self) -> dict:
        pass

    @abstractmethod
    async def execute(self, *args, **kwargs) -> str:
        pass

@dataclass
class FunctionCall:
    name: str
    arguments: Dict[str, Any]  # 要求附加 user_id 参数

def get_functions_schemas(functions: list[BaseFunction]) -> list[dict]:
    return [func.tool_schema for func in functions]


_all_tools: dict[str, BaseFunction] = {}

def register_tool(tool):
    if isinstance(tool, type): # 如果传入的是类，则实例化
        tool = tool()
    if tool.tool_schema["name"] not in _all_tools:
        logger.debug(f"注册工具: {tool.tool_schema['name']} -> {tool.__class__.__name__}")
        _all_tools[tool.tool_schema["name"]] = tool

def get_all_tools() -> Dict[str, BaseFunction]:
    return _all_tools

async def auto_execute_tool(function_call: FunctionCall) -> str:
    tool = _all_tools.get(function_call.name)
    if not tool:
        logger.error(f"LLM调用了未注册的工具: {function_call.name}")
        return "This tool is not registered and cannot be executed."

    logger.trace(f"调用工具: {function_call.name}, 参数: {function_call.arguments}")
    if function_call.arguments.get("user_id") is None:
        logger.warning(f"调用工具 {function_call.name} 时未提供 user_id 参数，可能无法正确执行")
    
    return await tool.execute(**function_call.arguments)

__all__ = ["BaseFunction", "get_functions_schemas", "register_tool", "auto_execute_tool", "get_all_tools", "FunctionCall"]
