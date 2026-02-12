from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

class LLMClient(ABC):
    @abstractmethod
    async def generate_response(self, user_id: int, context: List[Dict[str, str]]) -> str:
        pass

__all__ = ["LLMClient"]