import datetime
from .state_manager import AmayaState

class World:
    """世界模拟器"""
    def __init__(self, state: AmayaState):
        self.state = state

    def tick(self):
        # 更新为当前的真实系统时间
        self.state.current_time = datetime.datetime.now()
