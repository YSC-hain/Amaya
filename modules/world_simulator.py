import datetime

class World:
    """与真实世界时间同步的世界模拟器。"""
    def __init__(self):
        self.current_time = datetime.datetime.now()

    def get_status(self):
        return f"时间: {self.current_time.strftime('%Y-%m-%d %H:%M:%S')}"

    def tick(self):
        # 更新为当前的真实系统时间
        self.current_time = datetime.datetime.now()
