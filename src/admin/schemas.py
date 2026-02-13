from __future__ import annotations

import asyncio
from dataclasses import dataclass

from pydantic import BaseModel, Field


@dataclass
class RuntimeControl:
    shutdown_event: asyncio.Event
    restart_event: asyncio.Event
    started_at: float


class ShutdownRequest(BaseModel):
    reason: str = Field(default="manual")
