from .state_manager import AmayaState

class Physiology:
    """最简单的生理模型。"""
    def __init__(self, state: AmayaState):
        self.state = state
        self.last_update_minute = -1

    def tick(self, current_minute):
        # 为了匹配真实时间，我们只在分钟变化时才更新精力
        if current_minute != self.last_update_minute:
            # 精力随时间缓慢下降 (大约每10分钟下降0.1)
            if self.state.energy > 0:
                self.state.energy -= 0.01 
            self.last_update_minute = current_minute
