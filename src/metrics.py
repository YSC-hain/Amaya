"""
一个简单的运行时指标收集类，用于统计 LLM 调用次数、消息流量等信息，方便后续扩展和监控。
"""

from __future__ import annotations

import time
from dataclasses import dataclass


@dataclass
class RuntimeMetrics:
    llm_call_count: int = 0
    llm_total_latency_ms: float = 0.0
    llm_error_count: int = 0
    msg_in_count: int = 0
    msg_out_count: int = 0
    reminder_triggered_count: int = 0
    last_llm_call_at: float | None = None

    def record_llm_call(self, latency_ms: float, error: bool = False) -> None:
        self.llm_call_count += 1
        self.llm_total_latency_ms += max(0.0, latency_ms)
        self.last_llm_call_at = time.time()
        if error:
            self.llm_error_count += 1

    def record_msg_in(self) -> None:
        self.msg_in_count += 1

    def record_msg_out(self) -> None:
        self.msg_out_count += 1

    def record_reminder_triggered(self) -> None:
        self.reminder_triggered_count += 1

    def snapshot(self) -> dict:
        avg_latency_ms = 0.0
        if self.llm_call_count > 0:
            avg_latency_ms = self.llm_total_latency_ms / self.llm_call_count

        return {
            "llm_call_count": self.llm_call_count,
            "llm_error_count": self.llm_error_count,
            "llm_total_latency_ms": round(self.llm_total_latency_ms, 2),
            "llm_avg_latency_ms": round(avg_latency_ms, 2),
            "msg_in_count": self.msg_in_count,
            "msg_out_count": self.msg_out_count,
            "reminder_triggered_count": self.reminder_triggered_count,
            "last_llm_call_at_epoch": self.last_llm_call_at,
            "last_llm_call_at_utc": (
                time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(self.last_llm_call_at))
                if self.last_llm_call_at is not None
                else None
            ),
        }


runtime_metrics = RuntimeMetrics()


__all__ = ["RuntimeMetrics", "runtime_metrics"]