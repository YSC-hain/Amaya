from .state_manager import AmayaState

class Psychology:
    """心理模型，包含输入验证和边界检查。"""
    
    VALID_MOODS = {
        "快乐", "开心", "兴奋", "满足", "平静", "放松", "无聊", "困惑", 
        "担心", "焦虑", "伤心", "失望", "愤怒", "恐惧", "害羞", "害怕",
        "好奇", "期待", "感激", "自豪", "内疚", "羞耻", "嫉妒", "孤独"
    }
    
    def __init__(self, state: AmayaState):
        if not state:
            raise ValueError("AmayaState cannot be None")
        self.state = state

    def set_mood(self, new_mood: str):
        """由LLM直接设置新的情绪，包含输入验证。"""
        if not isinstance(new_mood, str):
            print(f"[警告] 情绪值必须是字符串，收到: {type(new_mood)}")
            return
        
        new_mood = new_mood.strip()
        if not new_mood:
            print("[警告] 情绪值不能为空")
            return
            
        # 如果情绪不在预定义列表中，仍然接受但记录警告
        if new_mood not in self.VALID_MOODS:
            print(f"[警告] 未识别的情绪值: {new_mood}")
        
        self.state.mood = new_mood

    def update_favorability(self, change: int):
        """根据LLM的决策更新好感度，包含边界检查。"""
        if not isinstance(change, (int, float)):
            print(f"[警告] 好感度变化值必须是数字，收到: {type(change)}")
            return
        
        # 转换为整数
        change = int(change)
        
        # 计算新的好感度值
        new_favorability = self.state.favorability + change
        
        # 限制在 0-100 范围内
        new_favorability = max(0, min(100, new_favorability))
        
        # 记录变化
        actual_change = new_favorability - self.state.favorability
        if actual_change != change:
            print(f"[信息] 好感度变化被限制：原计划{change}，实际{actual_change}")
        
        self.state.favorability = new_favorability
