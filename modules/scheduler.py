import re
from .state_manager import AmayaState

class Scheduler:
    """日程安排器，包含输入验证和状态管理。"""
    def __init__(self, state: AmayaState):
        if not state:
            raise ValueError("AmayaState cannot be None")
        self.state = state
        self.schedule = {
            "09:00": "是时候学习新东西了！",
            "22:00": "是时候睡觉了。"
        }

    def _validate_time_format(self, time_str: str) -> bool:
        """验证时间格式是否为 HH:MM。"""
        if not isinstance(time_str, str):
            return False
        # 使用正则表达式验证格式
        pattern = r'^([01]?[0-9]|2[0-3]):[0-5][0-9]$'
        return re.match(pattern, time_str) is not None
    
    def get_task_for_time(self, time_str: str):
        """获取指定时间的任务，包含输入验证。"""
        # 验证时间格式
        if not self._validate_time_format(time_str):
            print(f"[警告] 无效的时间格式: {time_str}，预期格式为 HH:MM")
            return None
            
        task = self.schedule.get(time_str)
        if task:
            # 验证 task 是字符串且不为空
            if isinstance(task, str) and task.strip():
                self.state.current_action = task.strip()
            else:
                print(f"[警告] 任务内容无效: {task}")
                return None
        return task
