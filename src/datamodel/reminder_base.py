from dataclasses import dataclass

__all__ = ["Reminder"]

@dataclass
class Reminder:
    reminder_id: int
    user_id: int
    title: str
    remind_at_utc: str  # 格式: "YYYY-MM-DD HH:MM"
    prompt: str
    status: str = "pending"  # 'pending', 'sent', 'acked', 'snoozed', 'escalated', 'ignored', 'cancelled'
    next_action_at_utc: str = None  # 格式: "YYYY-MM-DD HH:MM"
