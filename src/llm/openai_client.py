from logger import logger
from config.settings import (
    OPENAI_PRIMARY_API_KEY,
    OPENAI_PRIMARY_BASE_URL,
    LLM_MAIN_MODEL,
)
from llm.base import LLMClient, LLMContextItem
from functions.base import get_all_tools, get_functions_schemas, auto_execute_tool, FunctionCall
from openai import AsyncOpenAI
from openai.types.responses import ResponseFunctionToolCall
from typing import Any, Dict, List
import json

class OpenAIClient(LLMClient):
    def __init__(
        self,
        api_key: str = OPENAI_PRIMARY_API_KEY,
        base_url: str = OPENAI_PRIMARY_BASE_URL,
        model: str = LLM_MAIN_MODEL,
        inst: str = "",
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.inst = inst
        self.client = AsyncOpenAI(
            api_key=self.api_key,
            base_url=self.base_url
        )

    def _convert_context_to_openai(self, context: List[LLMContextItem]) -> List[Any]:
        role_dict = {
            "system": "system",
            "world": "developer",
            "user": "user",
            "amaya": "assistant",
        }
        type_list = ["function_call_output", "reasoning"]

        converted: List[Any] = []
        for item in context:
            if isinstance(item, ResponseFunctionToolCall):
                converted.append(item)
                continue

            if not isinstance(item, dict):
                continue

            if item.get("type") in type_list:
                converted.append(dict(item))
                continue

            role = item.get("role")
            if role in role_dict:
                converted.append({
                    "role": role_dict[role],
                    "content": item.get("content", ""),
                })

        return converted


    async def generate_response(
        self,
        user_id: int,
        context: List[LLMContextItem],
        append_inst: str | None = None,
        allow_tools: bool = True, # 未来应该拓展为“允许使用的工具集”
    ) -> str:
        request_context: List[Any] = list(context)

        # Disable tools for deterministic, side-effect-free generations.
        if not allow_tools:
            logger.trace(f"LLM请求发起(禁用工具) BaseUrl:{self.base_url}; Model:{self.model}; Context:{context}")
            response = await self.client.responses.create(
                model=self.model,
                instructions=self.inst + (append_inst or ""),
                input=self._convert_context_to_openai(request_context),
                tools=[],
                tool_choice="none",
            )
            logger.trace(f"LLM请求收到响应: {response}")
            return response.output_text

        need_while = True
        while need_while:
            logger.trace(f"LLM请求发起 BaseUrl:{self.base_url}; Model:{self.model}; Context:{context}")
            response = await self.client.responses.create(
                model=self.model,
                instructions=self.inst + (append_inst or ""),
                tools=get_functions_schemas(list(get_all_tools().values())),
                input=self._convert_context_to_openai(request_context),
            )
            logger.trace(f"LLM请求收到响应: {response}")

            # Function Call Handling  docs: https://platform.openai.com/docs/guides/function-calling
            need_while = False
            for item in response.output:
                if item.type == "function_call":
                    need_while = True
                    request_context.append(item)

                    arguments = json.loads(item.arguments)
                    arguments["user_id"] = user_id  # 附加 user_id 参数
                    res = await auto_execute_tool(FunctionCall(name=item.name, arguments=arguments))
                    request_context.append({
                        "type": "function_call_output",
                        "call_id": item.call_id,
                        "output": json.dumps({item.name: res}),
                    })

        return response.output_text or ""
