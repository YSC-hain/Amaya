class Memory:
    """最简单的记忆模型。"""
    def __init__(self):
        self.short_term_memory = []
        self.long_term_memory = {}

    def add_memory(self, text: str):
        # 添加到短期记忆，只保留最近10次交互
        self.short_term_memory.append(text)
        if len(self.short_term_memory) > 10:
            self.short_term_memory.pop(0)

    def get_status(self):
        return f"短期记忆条数: {len(self.short_term_memory)}"
