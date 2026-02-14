import asyncio
import json
from typing import Any, Dict, List, Tuple

from google import genai
from google.genai import types

from config.settings import GEMINI_API_KEY, GEMINI_BASE_URL, LLM_MAIN_MODEL
from datamodel import FunctionCall
from functions.base import auto_execute_tool, get_all_tools, get_functions_schemas
from llm.base import LLMClient, LLMContextItem
from logger import logger


class GeminiClient(LLMClient):
    WORLD_PREFIX = "[WORLD_CONTEXT]"
    FALLBACK_TEXT = "抱歉，我刚刚没能稳定生成回复。请稍后再试。"
    MAX_LOOP_STEPS = 12
    MAX_MALFORMED_RETRIES = 1
    MAX_DISABLE_TOOLS_REPROMPTS = 1
    API_RETRY_DELAYS_SECONDS = [5.0, 15.0]

    def __init__(self, base_url: str = GEMINI_BASE_URL, api_key: str = GEMINI_API_KEY, model: str = LLM_MAIN_MODEL, inst: str = "") -> None:
        self.model = model
        self.inst = inst
        self.client = genai.Client(api_key=api_key, http_options={"base_url": base_url} if base_url else None)

    @staticmethod
    def _text_message(role: str, text: str) -> Dict[str, Any]:
        return {
            "role": role,
            "parts": [{"text": text}],
        }

    @staticmethod
    def _is_retryable_error(error: Exception) -> bool:
        msg = str(error).lower()
        signals = [
            "429",
            "rate limit",
            "resource_exhausted",
            "temporarily unavailable",
            "timeout",
            "timed out",
            "503",
            "502",
            "504",
            "connection reset",
            "connection aborted",
            "upstream_error",
        ]
        return any(s in msg for s in signals)

    def _convert_context_to_gemini(self, context: List[LLMContextItem]) -> Tuple[List[Dict[str, Any]], str]:
        converted: List[Dict[str, Any]] = []
        system_parts: List[str] = []

        for item in context:
            if not isinstance(item, dict):
                continue

            if item.get("role") == "system":
                system_parts.append(item.get("content", ""))
                continue

            if "parts" in item and item.get("role") in ("user", "model"):
                converted.append({
                    "role": item.get("role"),
                    "parts": item.get("parts", []),
                })
                continue

            role = item.get("role")
            content = item.get("content", "")
            if role == "world":
                converted.append(self._text_message("user", f"{self.WORLD_PREFIX}\n{content}"))
            elif role == "user":
                converted.append(self._text_message("user", content))
            elif role in ("amaya", "assistant"):
                converted.append(self._text_message("model", content))

        return converted, "\n\n".join(p for p in system_parts if p.strip())

    def _build_gemini_tools(self) -> List[types.Tool]:
        declarations: List[types.FunctionDeclaration] = []
        for schema in get_functions_schemas(list(get_all_tools().values())):
            if schema.get("type") != "function":
                continue
            declarations.append(
                types.FunctionDeclaration(
                    name=schema.get("name", ""),
                    description=schema.get("description", ""),
                    parameters=schema.get("parameters", {"type": "object", "properties": {}}),
                )
            )

        if not declarations:
            return []
        return [types.Tool(function_declarations=declarations)]

    def _extract_parts(self, response: Any) -> List[Any]:
        candidates = getattr(response, "candidates", None) or []
        if not candidates:
            return []
        content = getattr(candidates[0], "content", None)
        if content is None:
            return []
        return list(getattr(content, "parts", None) or [])

    def _extract_model_content(self, response: Any) -> Any | None:
        candidates = getattr(response, "candidates", None) or []
        if not candidates:
            return None

        candidate = candidates[0]
        content = getattr(candidate, "content", None)
        if content is not None:
            return content

        if isinstance(candidate, dict):
            return candidate.get("content")

        return None

    def _extract_finish_reason(self, response: Any) -> str:
        candidates = getattr(response, "candidates", None) or []
        if not candidates:
            return ""

        candidate = candidates[0]
        finish_reason = getattr(candidate, "finish_reason", None)
        if finish_reason is None and isinstance(candidate, dict):
            finish_reason = candidate.get("finish_reason")

        if finish_reason is None:
            return ""
        if hasattr(finish_reason, "name"):
            return str(getattr(finish_reason, "name", "") or "")

        raw = str(finish_reason)
        if "MALFORMED_FUNCTION_CALL" in raw:
            return "MALFORMED_FUNCTION_CALL"
        return raw

    def _coerce_arguments(self, raw_args: Any) -> Dict[str, Any]:
        if raw_args is None:
            return {}
        if isinstance(raw_args, dict):
            return dict(raw_args)
        try:
            return dict(raw_args)
        except Exception:
            pass
        try:
            return json.loads(json.dumps(raw_args))
        except Exception:
            return {}

    def _extract_function_calls(self, parts: List[Any]) -> List[Tuple[str, Dict[str, Any]]]:
        function_calls: List[Tuple[str, Dict[str, Any]]] = []
        for part in parts:
            function_call = getattr(part, "function_call", None)
            if function_call is None and isinstance(part, dict):
                function_call = part.get("function_call")
            if function_call is None:
                continue

            name = getattr(function_call, "name", None)
            if name is None and isinstance(function_call, dict):
                name = function_call.get("name")
            if not name:
                continue

            args = getattr(function_call, "args", None)
            if args is None and isinstance(function_call, dict):
                args = function_call.get("args")

            function_calls.append((name, self._coerce_arguments(args)))

        return function_calls

    def _extract_text(self, response: Any, parts: List[Any]) -> str:
        text = getattr(response, "text", None)
        if isinstance(text, str) and text.strip():
            return text

        text_parts: List[str] = []
        for part in parts:
            part_text = getattr(part, "text", None)
            if part_text is None and isinstance(part, dict):
                part_text = part.get("text")
            if isinstance(part_text, str) and part_text.strip():
                text_parts.append(part_text)
        return "\n".join(text_parts).strip()

    async def _generate_once(self, request_context: List[Any], config: types.GenerateContentConfig) -> Any:
        return await asyncio.to_thread(
            self.client.models.generate_content,
            model=self.model,
            contents=request_context,
            config=config,
        )

    async def _generate_once_with_retry(self, request_context: List[Any], config: types.GenerateContentConfig) -> Any:
        for idx, delay in enumerate([0.0, *self.API_RETRY_DELAYS_SECONDS]):
            try:
                if delay > 0:
                    await asyncio.sleep(delay)
                return await self._generate_once(request_context, config)
            except Exception as e:
                is_last = idx == len(self.API_RETRY_DELAYS_SECONDS)
                if is_last or not self._is_retryable_error(e):
                    raise
                logger.warning(
                    f"Gemini 请求暂时失败，准备重试: attempt={idx + 1}/{len(self.API_RETRY_DELAYS_SECONDS) + 1}, delay={self.API_RETRY_DELAYS_SECONDS[idx]}s, error={e}"
                )

        raise RuntimeError("Gemini 请求重试异常退出")

    async def generate_response(
        self,
        user_id: int,
        context: List[LLMContextItem],
        append_inst: str | None = None,
        allow_tools: bool = True,
    ) -> str:
        request_context, system_from_context = self._convert_context_to_gemini(context)
        system_instruction = self.inst + (append_inst or "")
        if system_from_context:
            system_instruction = f"{system_instruction}\n\n{system_from_context}" if system_instruction else system_from_context

        config_kwargs: Dict[str, Any] = {
            "system_instruction": system_instruction,
        }
        if allow_tools:
            config_kwargs["tools"] = self._build_gemini_tools()
        config = types.GenerateContentConfig(**config_kwargs)

        malformed_retry_budget = self.MAX_MALFORMED_RETRIES
        disable_tools_reprompt_budget = self.MAX_DISABLE_TOOLS_REPROMPTS
        loop_budget = self.MAX_LOOP_STEPS
        while True:
            loop_budget -= 1
            if loop_budget < 0:
                logger.error("Gemini 响应循环超过上限，返回兜底回复")
                return self.FALLBACK_TEXT

            logger.trace(f"Gemini请求发起 Model:{self.model}; Context:{request_context}")
            response = await self._generate_once_with_retry(request_context, config)
            logger.trace(f"Gemini请求收到响应: {response}")

            finish_reason = self._extract_finish_reason(response)
            if finish_reason == "MALFORMED_FUNCTION_CALL":
                logger.warning("Gemini 返回 MALFORMED_FUNCTION_CALL，准备修复性重试")
                if malformed_retry_budget > 0:
                    malformed_retry_budget -= 1
                    if allow_tools:
                        request_context.append(self._text_message(
                            "user",
                            "你上一轮的函数调用格式无效。请重新生成：若需要调用工具，仅输出合法函数调用；否则直接输出文本回复。"
                        ))
                    else:
                        request_context.append(self._text_message(
                            "user",
                            "工具调用已禁用。请直接输出自然语言文本，不要输出任何函数调用。"
                        ))
                    continue
                logger.error("Gemini 返回 MALFORMED_FUNCTION_CALL 且重试后仍失败，返回兜底回复")
                return self.FALLBACK_TEXT

            parts = self._extract_parts(response)
            function_calls = self._extract_function_calls(parts)
            if function_calls and not allow_tools:
                logger.warning("Gemini 在禁用工具时仍返回函数调用，要求其改为纯文本回复")
                if disable_tools_reprompt_budget <= 0:
                    logger.error("Gemini 在禁用工具模式持续返回函数调用，返回兜底回复")
                    return self.FALLBACK_TEXT
                disable_tools_reprompt_budget -= 1
                request_context.append(self._text_message("user", "工具调用不可用。请仅输出纯文本回复。"))
                continue

            if not function_calls:
                text = self._extract_text(response, parts)
                if text.strip():
                    return text
                logger.error("Gemini 返回空文本回复，返回兜底回复")
                return self.FALLBACK_TEXT

            # 必须原样回传模型输出的 function_call parts，保留 thought_signature 等内部字段。
            model_content = self._extract_model_content(response)
            if model_content is not None:
                request_context.append(model_content)
            else:
                logger.warning("Gemini 未返回可复用的 candidate content，回退到手工构造 function_call parts")
                model_call_parts = [{"function_call": {"name": name, "args": arguments}} for name, arguments in function_calls]
                request_context.append({"role": "model", "parts": model_call_parts})

            for name, arguments in function_calls:
                call_arguments = dict(arguments)
                call_arguments["user_id"] = user_id
                result = await auto_execute_tool(FunctionCall(name=name, arguments=call_arguments))
                request_context.append({
                    "role": "user",
                    "parts": [{
                        "function_response": {
                            "name": name,
                            "response": {"result": result},
                        }
                    }],
                })
