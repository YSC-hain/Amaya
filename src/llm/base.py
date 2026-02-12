from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from enum import Enum
from datetime import datetime

class LLMClient(ABC):
    @abstractmethod
    async def generate_response(self, user_id: int, context: List[Dict[str, str]]) -> str:
        pass

__all__ = ["LLMClient"]