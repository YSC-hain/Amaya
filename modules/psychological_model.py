from .state_manager import AmayaState

class Psychology:
    """最简单的心理模型。"""
    def __init__(self, state: AmayaState):
        self.state = state

    def set_mood(self, new_mood: str):
        """由LLM直接设置新的情绪。"""
        self.state.mood = new_mood

    def update_favorability(self, change: int):
        """根据LLM的决策更新好感度。"""
        self.state.favorability += change
