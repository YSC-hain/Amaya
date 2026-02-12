from logger import logger
from config.settings import (
    OPENAI_PRIMARY_API_KEY,
    OPENAI_PRIMARY_BASE_URL,
    LLM_MAIN_MODEL,
    LLM_FAST_MODEL,
)
from llm.base import *
from functions.base import get_all_tools, get_functions_schemas, auto_execute_tool, FunctionCall
from openai import AsyncOpenAI
from openai.types.responses import ResponseFunctionToolCall
from typing import List, Dict
import json

class OpenAIClient(LLMClient):
    def __init__(self, api_key: str = OPENAI_PRIMARY_API_KEY, base_url: str = OPENAI_PRIMARY_BASE_URL, model: str = LLM_MAIN_MODEL, inst: str = "" ) -> None:
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.inst = inst
        self.client = AsyncOpenAI(
            api_key = self.api_key,
            base_url = self.base_url
        )

    
    def _convert_context_to_openai(self, context: List[Dict[str, str]]) -> List[Dict[str, str]]:
        role_dict = {
            "system": "system",
            "world": "developer",
            "user": "user",
            "amaya": "assistant",
        }
        type_list = ["function_call_output", "reasoning"]

        converted = []
        for item in context:
            if isinstance(item, ResponseFunctionToolCall):
                converted.append(item)
            if isinstance(item, Dict) and item.get("type") in type_list:
                converted.append(item)
            if isinstance(item, Dict) and item.get("role") in role_dict:
                item["role"] = role_dict[item["role"]]
                converted.append(item)

        return converted


    async def generate_response(
        self,
        user_id: int,
        context: List[Dict[str, str]],
        append_inst: str | None = None,
        allow_tools: bool = True, # 未来应该拓展为“允许使用的工具集”
    ) -> str:

        # Disable tools for deterministic, side-effect-free generations.
        if not allow_tools:
            logger.trace(f"LLM请求发起(禁用工具) BaseUrl:{self.base_url}; Model:{self.model}; Context:{context}")
            response = await self.client.responses.create(
                model=self.model,
                instructions=self.inst + (append_inst or ""),
                input=self._convert_context_to_openai(context),
                tools=[],
                tool_choice="none",
            )
            logger.trace(f"LLM请求收到响应: {response}")
            return response.output_text

        need_while = True
        while need_while:
            logger.trace(f"LLM请求发起 BaseUrl:{self.base_url}; Model:{self.model}; Context:{context}")
            response = await self.client.responses.create(
                model = self.model,
                instructions = self.inst + (append_inst or ""),
                tools = get_functions_schemas(list(get_all_tools().values())),
                input = self._convert_context_to_openai(context),
            )
            logger.trace(f"LLM请求收到响应: {response}")

            # Function Call Handling  docs: https://platform.openai.com/docs/guides/function-calling
            need_while = False
            for item in response.output:
                if item.type == "function_call":
                    need_while = True
                    context.append(item)

                    arugments = json.loads(item.arguments)
                    arugments["user_id"] = user_id  # 附加 user_id 参数
                    res = await auto_execute_tool(FunctionCall(name=item.name, arguments=arugments))
                    context.append({
                        "type": "function_call_output",
                        "call_id": item.call_id,
                        "output": json.dumps({
                            item.name: res
                        })
                    })

        return response.output_text
