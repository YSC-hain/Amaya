class Physiology:
    """最简单的生理模型。"""
    def __init__(self):
        self.energy = 80  # 范围 0-100
        self.last_update_minute = -1

    def get_status(self):
        # 将精力值格式化为整数，避免过多小数
        return f"精力: {int(self.energy)}/100"

    def tick(self, current_minute):
        # 为了匹配真实时间，我们只在分钟变化时才更新精力
        if current_minute != self.last_update_minute:
            # 精力随时间缓慢下降 (大约每10分钟下降0.1)
            if self.energy > 0:
                self.energy -= 0.01 
            self.last_update_minute = current_minute
