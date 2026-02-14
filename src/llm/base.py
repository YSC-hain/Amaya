from abc import ABC, abstractmethod
from typing import Any, Dict, List, Literal, TypedDict, Union

__all__ = ["LLMClient", "LLMContextItem", "LLMMessage", "LLMToolContextItem"]

class LLMMessage(TypedDict):
    role: Literal["system", "world", "user", "amaya"]
    content: str


class LLMToolContextItem(TypedDict, total=False):
    type: str
    call_id: str
    output: str


LLMContextItem = Union[LLMMessage, LLMToolContextItem, Dict[str, Any]]


class LLMClient(ABC):
    @abstractmethod
    async def generate_response(
        self,
        context: List[LLMContextItem],
        append_inst: str | None = None,
        allow_tools: bool = True,
    ) -> str:
        pass
