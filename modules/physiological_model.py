from .state_manager import AmayaState

class Physiology:
    """生理模型，包含边界检查和输入验证。"""
    def __init__(self, state: AmayaState):
        if not state:
            raise ValueError("AmayaState cannot be None")
        self.state = state
        self.last_update_minute = -1

    def tick(self, current_minute):
        """生理状态更新，包含输入验证和边界检查。"""
        # 验证输入
        if not isinstance(current_minute, int) or not (0 <= current_minute <= 59):
            print(f"[警告] 无效的分钟值: {current_minute}")
            return
            
        # 为了匹配真实时间，我们只在分钟变化时才更新精力
        if current_minute != self.last_update_minute:
            # 精力随时间缓慢下降 (基础情况大约每10分钟下降0.1)
            # 使用 max 确保精力不会变成负数
            self.state.energy = max(0.0, self.state.energy - 0.01)
            self.last_update_minute = current_minute
