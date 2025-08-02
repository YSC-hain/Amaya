from .state_manager import AmayaState
import google.generativeai as genai
import config
import threading
from .persistence_manager import PersistenceManager

class Memory:
    """管理短期和长期记忆，并确保线程安全。"""
    def __init__(self, state: AmayaState, persistence_manager: PersistenceManager):
        self.state = state
        self.persistence_manager = persistence_manager
        self.lock = threading.Lock() # 为内存操作添加线程锁
        # 初始化 genai 客户端以用于计算 token
        genai.configure(api_key=config.API_KEY, transport="rest", client_options={"api_endpoint": config.API_ENDPOINT})
        self.model = genai.GenerativeModel(model_name=config.MODEL_ID)

    def add_memory(self, role: str, content: str) -> dict:
        """
        添加一条新的记忆到内存中，并维护短期记忆的Token限制。
        返回创建的记忆字典，以便调用者可以将其持久化。
        """
        with self.lock: # 确保在任何时候只有一个线程可以修改内存
            # 1. 创建新的记忆条目
            new_memory = {
                "role": role,
                "content": content,
                "timestamp": self.state.current_time.strftime('%Y-%m-%d %H:%M:%S')
            }

            # 2. 添加到短期和长期记忆中
            self.state.short_term_memory.append(new_memory)
            self.state.full_memory_archive.append(new_memory)

            # 3. 检查并修剪短期记忆，直到满足Token限制
            self.prune_short_term_memory()
            
            # 4. 返回新创建的记忆，由调用者负责持久化
            return new_memory


    def get_short_term_memory_for_prompt(self) -> list[dict]:
        """为Prompt准备短期记忆，并在每条消息前加上时间戳。"""
        with self.lock:
            # 创建一个新的列表，其中包含带有时间戳的格式化消息
            formatted_memory = []
            for mem in self.state.short_term_memory:
                formatted_content = f"[{mem['timestamp']}] {mem['content']}"
                formatted_memory.append({
                    "role": mem["role"],
                    "content": formatted_content
                })
            return formatted_memory

    def prune_short_term_memory(self):
        """如果短期记忆超过Token限制，则从最旧的开始移除。此方法应在锁的保护下调用。"""
        while True:
            # 将短期记忆格式化为单一字符串以计算token
            formatted_memory = [f"{mem['role']}: {mem['content']} at {mem['timestamp']}" for mem in self.state.short_term_memory]
            memory_string = "\n".join(formatted_memory)
            
            # 计算当前token
            try:
                token_count = self.model.count_tokens(memory_string).total_tokens
            except Exception:
                # 如果API调用失败，则退回到基于条数的限制
                if len(self.state.short_term_memory) > 20:
                    self.state.short_term_memory.pop(0)
                break

            # 如果token数量在限制内，则停止修剪
            if token_count <= config.SHORT_TERM_MEMORY_TOKEN_LIMIT:
                break
            
            # 如果超出限制且内存中还有条目，则移除最旧的一条
            if len(self.state.short_term_memory) > 0:
                self.state.short_term_memory.pop(0)
            else:
                break # 避免无限循环

    def rebuild_short_term_from_full_archive(self):
        """从完整的记忆存档中重建短期记忆。"""
        with self.lock:
            self.state.short_term_memory.clear()
            # 简单地从完整存档的末尾开始填充
            self.state.short_term_memory.extend(self.state.full_memory_archive)
            # 然后修剪到符合token限制
            self.prune_short_term_memory()
