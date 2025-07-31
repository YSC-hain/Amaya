import datetime
from typing import Optional, Dict, Any, List

class AmayaState:
    """一个集中的数据容器，存放Amaya所有可变的实时数据。"""
    def __init__(self, user_id: str = None):
        # 用户标识
        self.user_id: Optional[str] = user_id

        # 世界状态
        self.current_time: datetime.datetime = datetime.datetime.now()

        # 生理状态
        self.energy: float = 80.0  # 范围 0-100

        # 心理状态
        self.mood: str = "平静"  # 例如: 平静, 开心, 伤心
        self.favorability: int = 50  # 范围 0-100

        # 记忆
        self.short_term_memory: List[Dict[str, Any]] = [] 
        self.full_memory_archive: List[Dict[str, Any]] = []

        # 行动与交互状态
        self.current_action: str = "无所事事"
        self.interaction_mode: str = "CHATTING" # CHATTING 或 LISTENING
        # 用于在任务被中断时，保存未完成的上下文
        self.interruption_context: Optional[Dict[str, Any]] = None