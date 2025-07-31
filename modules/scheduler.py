from .state_manager import AmayaState

class Scheduler:
    """最简单的日程安排器。"""
    def __init__(self, state: AmayaState):
        self.state = state
        self.schedule = {
            "09:00": "是时候学习新东西了！",
            "22:00": "是时候睡觉了。"
        }

    def get_task_for_time(self, time_str: str):
        # time_str 的格式应该是 "HH:MM"
        task = self.schedule.get(time_str)
        if task:
            self.state.current_action = task
        return task
