import datetime
from .state_manager import AmayaState

class World:
    """与真实世界时间同步的世界模拟器。"""
    def __init__(self, state: AmayaState):
        self.state = state

    def tick(self):
        # 更新为当前的真实系统时间
        self.state.current_time = datetime.datetime.now()
