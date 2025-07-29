import google.generativeai as genai
import json
import config
from .logger import log_llm_interaction
from .prompt_manager import PromptManager

class Agent:
    """使用 genai SDK 和结构化输出生成响应的自主代理。"""
    def __init__(self, world, physiology, psychology, memory):
        self.world = world
        self.physiology = physiology
        self.psychology = psychology
        self.memory = memory
        self.prompt_manager = PromptManager()

        genai.configure(
            api_key=config.API_KEY,
            transport="rest",
            client_options={"api_endpoint": config.API_ENDPOINT}
        )

    def _get_internal_state_json(self):
        state = {
            "world_status": self.world.get_status(),
            "physiology_status": self.physiology.get_status(),
            "psychology_status": self.psychology.get_status()
        }
        return json.dumps(state, ensure_ascii=False, indent=2)

    def generate_response(self, user_input: str):
        self.memory.add_memory(f"用户: {user_input}")
        # 注意：旧的基于关键词的好感度更新逻辑已移除，完全依赖LLM

        internal_state_str = self._get_internal_state_json()
        system_prompt = self.prompt_manager.render_system_prompt({"internal_state": internal_state_str})
        json_schema = self.prompt_manager.get_json_schema()
        
        generation_config = genai.types.GenerationConfig(
            response_mime_type="application/json",
            response_schema=json_schema,
            temperature=1.0, # 调高温度以鼓励更复杂的思考链
            top_p=0.95,
            max_output_tokens=2048 # 增加Token以容纳更长的思考过程
        )

        model = genai.GenerativeModel(
            model_name=config.MODEL_ID,
            system_instruction=system_prompt,
            generation_config=generation_config
        )

        history = []
        for mem in self.memory.short_term_memory:
            role, text = mem.split(": ", 1)
            history.append({"role": "user" if role == "用户" else "model", "parts": [text]})

        payload_for_log = {"system_prompt": system_prompt, "history": history, "generation_config": generation_config}
        try:
            chat_session = model.start_chat(history=history[:-1])
            response = chat_session.send_message(history[-1]["parts"][0])
            raw_json_text = response.candidates[0].content.parts[0].text

            try:
                structured_data = json.loads(raw_json_text)
                log_llm_interaction(payload_for_log, structured_data)
            except json.JSONDecodeError as e:
                error_str = f"JSON解析失败: {e}. 原始文本: {raw_json_text}"
                log_llm_interaction(payload_for_log, raw_json_text, error=error_str)
                print(f"\n[错误] {error_str}")
                return [{
                    "delay seconds": 1, 
                    "content": "哎呀，我好像思路有点乱，没组织好语言，我们换个话题或者你再说一遍好吗？"
                }]

            # --- 全面适配新的JSON结构 ---
            # 1. 更新情绪
            new_mood = structured_data.get("4_new mood", self.psychology.mood)
            self.psychology.set_mood(new_mood)

            # 2. 更新好感度
            favorability_change = structured_data.get("8_Changes in favorability", 0)
            self.psychology.favorability += favorability_change

            # 3. 判断是否需要回复
            if not structured_data.get("5_require response", True):
                return None

            # 4. 提取最终回复
            response_object = structured_data.get("6_response", {})
            response_messages = response_object.get("3_response_release", [])
            
            for msg in response_messages:
                self.memory.add_memory(f"Amaya: {msg.get('content')}")

            return response_messages

        except Exception as e:
            error_str = str(e)
            log_llm_interaction(payload_for_log, None, error=f"SDK 调用失败: {error_str}")
            print(f"\n[错误] SDK 调用失败: {error_str}")
            return []