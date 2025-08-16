import google.generativeai as genai
import json
from typing import Optional, Dict, Any

import config
import emoji
from .logger import event_logger
from .prompt_manager import PromptManager
from .state_manager import AmayaState
from .psychological_model import Psychology
from .memory_manager import Memory

def contains_emoji(text):
    """检查字符串是否包含 emoji。"""
    return emoji.emoji_count(text) > 0

def remove_emojis(text):
    """从字符串中移除所有 emoji。"""
    return emoji.replace_emoji(text, replace='')

class Agent:
    """使用 genai SDK 和结构化输出生成响应的自主代理。"""
    def __init__(self, state: AmayaState, memory: Memory):
        self.state = state
        self.prompt_manager = PromptManager()
        self.psychology = Psychology(self.state)
        self.memory = memory

        genai.configure(
            api_key=config.API_KEY,
            transport="rest",
            client_options={"api_endpoint": config.API_ENDPOINT}
        )

    def _get_internal_state_json(self):
        state_dict = {
            "world_status": {
                "time": self.state.current_time.strftime('%Y-%m-%d %H:%M:%S')
            },'''
            "physiology_status": {
                "energy": f"{int(self.state.energy)}/100"
            },'''
            "psychology_status": {
                "mood": self.state.mood,
                "favorability": self.state.favorability
            },
            "current_action": self.state.current_action
        }
        return json.dumps(state_dict, ensure_ascii=False, indent=2)

    def _build_interruption_prompt(self, context: Dict[str, Any]) -> str:
        """构建中断提示。"""
        already_sent_str = '、'.join(context.get('already_sent', []))
        unsent_message = context.get('unsent_message', '')
        prompt = f"[系统提示：你的输出被打断了。你之前已经发送了“{already_sent_str}”，但你本来还想继续发送“{unsent_message}”。请结合用户最新的消息，自然地继续对话。]"
        return prompt

    def _build_listening_mode_prompt(self) -> str:
        """构建倾听模式提示。"""
        return "[系统提示：你现在处于倾听模式，请专注于鼓励用户继续讲述，并做出简短的回应。]"

    def generate_response(self, user_input: str, interruption_context: Optional[Dict[str, Any]] = None, interaction_mode: str = 'CHATTING'):
        internal_state_str = self._get_internal_state_json()
        system_prompt = self.prompt_manager.render_system_prompt({"internal_state": internal_state_str})
        json_schema = self.prompt_manager.get_json_schema()

        generation_config = genai.types.GenerationConfig(
            response_mime_type="application/json",
            response_schema=json_schema,
            temperature=1.0,
            top_p=0.95,
            max_output_tokens=8192
        )

        model = genai.GenerativeModel(
            model_name=config.MODEL_ID,
            system_instruction=system_prompt,
            generation_config=generation_config
        )

        # 构建上下文历史
        history = []
        # 首先添加临时的、仅用于本次调用的系统提示
        transient_prompts = []
        if interruption_context:
            transient_prompts.append(self._build_interruption_prompt(interruption_context))

        if interaction_mode == 'LISTENING':
            transient_prompts.append(self._build_listening_mode_prompt())
        
        if transient_prompts:
            # 将所有临时提示合并为一个用户消息
            combined_transient_prompt = "\n".join(transient_prompts)
            history.append({"role": "user", "parts": [{"text": combined_transient_prompt}]})

        # 然后添加从记忆中获取的对话历史
        grouped_messages = []
        for mem in self.memory.get_short_term_memory_for_prompt():
            llm_role = "user" if mem['role'] in ["用户", "系统提示"] else "model"
            
            if not grouped_messages or grouped_messages[-1]["role"] != llm_role:
                grouped_messages.append({"role": llm_role, "content": [mem['content']]})
            else:
                grouped_messages[-1]["content"].append(mem['content'])

        for group in grouped_messages:
            combined_content = "\n".join(group["content"])
            history.append({"role": group["role"], "parts": [{"text": combined_content}]})

        payload_for_log = {"system_prompt": system_prompt, "history": history, "generation_config": generation_config}
        event_logger.log_event('LLM_CALL_START', payload_for_log)

        try:
            chat_session = model.start_chat(history=history[:-1])
            response = chat_session.send_message(history[-1]["parts"][0])
            raw_json_text = response.candidates[0].content.parts[0].text

            try:
                structured_data = json.loads(raw_json_text)
                event_logger.log_event('LLM_CALL_SUCCESS', {'response': structured_data})
            except json.JSONDecodeError as e:
                error_str = f"JSON解析失败: {e}. 原始文本: {raw_json_text}"
                event_logger.log_event('LLM_CALL_ERROR', {'error': error_str, 'raw_response': raw_json_text})
                print(f"\n[错误] {error_str}")
                return [{
                    "delay seconds": 1,
                    "content": "哎呀，我好像思路有点乱，没组织好语言，我们换个话题或者你再说一遍好吗？"
                }]

            self.state.current_action = structured_data.get("1_doing", self.state.current_action)
            self.psychology.set_mood(structured_data.get("4_new mood", self.state.mood))
            self.psychology.update_favorability(structured_data.get("8_Changes in favorability", 0))

            new_mode = structured_data.get("9_set_interaction_mode")
            if new_mode and new_mode in ["CHATTING", "LISTENING"]:
                self.state.interaction_mode = new_mode

            if not structured_data.get("5_require response", True):
                return None

            response_object = structured_data.get("6_response", {})
            response_messages = response_object.get("3_response_release", [])

            for msg in response_messages:
                if contains_emoji(msg["content"]):
                    event_logger.log_event('EMOJI_FILTERED', {'original_content': msg["content"]})
                    msg["content"] = remove_emojis(msg["content"])

            return response_messages

        except Exception as e:
            error_str = str(e)
            event_logger.log_event('LLM_CALL_ERROR', {'error': f"SDK 调用失败: {error_str}"})
            print(f"\n[错误] SDK 调用失败: {error_str}")
            return []