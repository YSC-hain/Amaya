class Psychology:
    """最简单的心理模型。"""
    def __init__(self):
        self.mood = "平静"  # 例如: 平静, 开心, 伤心
        self.favorability = 50  # 0-100

    def get_status(self):
        return f"情绪: {self.mood}, 好感度: {self.favorability}"

    def set_mood(self, new_mood: str):
        """由LLM直接设置新的情绪。"""
        self.mood = new_mood

    def update_favorability(self, text: str):
        """根据用户输入微调好感度。这个逻辑可以保留，因为它独立于情绪。"""
        text_lower = text.lower()
        if "谢" in text_lower or "爱" in text_lower or "喜欢" in text_lower:
            self.favorability += 1
        elif "伤心" in text_lower or "难过" in text_lower or "坏" in text_lower:
            self.favorability -= 1
