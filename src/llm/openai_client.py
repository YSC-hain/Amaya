from config.logger import logger
from config.settings import (
    OPENAI_PRIMARY_API_KEY,
    OPENAI_PRIMARY_BASE_URL,
    LLM_MAIN_MODEL,
    LLM_FAST_MODEL,
)
from llm.base import *
from functions.base import get_all_tools, get_functions_schemas, auto_execute_tool, FunctionCall
from functions.reminder_func import *
from openai import OpenAI
from typing import List, Dict
import json

class OpenAIClient(LLMClient):
    def __init__(self, api_key: str = OPENAI_PRIMARY_API_KEY, base_url: str = OPENAI_PRIMARY_BASE_URL, model: str = LLM_MAIN_MODEL, inst: str = "" ) -> None:
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.inst = inst
        self.client = OpenAI(
            api_key = self.api_key,
            base_url = self.base_url
        )

    async def generate_response(self, context: List[Dict[str, str]]) -> str:
        need_while = True
        while need_while:
            logger.trace(f"LLM请求发起 BaseUrl:{self.base_url}; Model:{self.model}; Context:{context}")
            response = self.client.responses.create(
                model = self.model,
                instructions = self.inst,
                tools = get_functions_schemas(list(get_all_tools().values())),
                input = context,
            )
            logger.trace(f"LLM请求收到响应: {response}")
            context += response.output
            
            # Function Call Handling  docs: https://platform.openai.com/docs/guides/function-calling
            need_while = False
            for item in response.output:
                if item.type == "function_call":
                    need_while = True
                    res = await auto_execute_tool(FunctionCall(name=item.name, arguments=json.loads(item.arguments)))
                    context.append({
                        "type": "function_call_output",
                        "call_id": item.call_id,
                        "output": json.dumps({
                            item.name: res
                        })
                    })

        return response.output_text
