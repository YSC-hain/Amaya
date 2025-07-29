import re
import json

class PromptManager:
    """负责读取、解析和渲染 prompt.md 模板文件。"""
    def __init__(self, file_path='prompt.md'):
        self.file_path = file_path
        self.templates = self._load_and_parse()

    def _load_and_parse(self):
        """加载并解析prompt.md文件，将其分割成不同的部分。"""
        templates = {}
        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            parts = content.split('---')

            if len(parts) > 0:
                templates['system_prompt'] = self._extract_section(parts[0], "System Prompt")

            if len(parts) > 1:
                templates['dynamic_prompt'] = self._extract_section(parts[1], "Dynamic System Prompt")

            if len(parts) > 2:
                templates['structured_output'] = self._extract_section(parts[2], "Structured Output Json")

        except FileNotFoundError:
            raise FileNotFoundError(f"错误: 提示词文件未找到于 '{self.file_path}'")
        except Exception as e:
            raise RuntimeError(f"解析提示词文件时出错: {e}")

        return templates

    def _extract_section(self, part_content, section_name):
        """从文本块中提取指定部分的内容。"""
        header = f"# {section_name}"
        content = part_content.replace(header, '', 1).strip()
        return content

    def render_system_prompt(self, variables: dict):
        """渲染系统提示，并替换其中的占位符。"""
        template = self.templates.get('system_prompt', '')
        for key, value in variables.items():
            template = template.replace(f"{{{{{key}}}}}", str(value))
        return template

    def get_json_schema(self):
        """获取结构化输出的JSON Schema定义。"""
        match = re.search(r'```structured_output_json\n(.*)\n```', self.templates.get('structured_output', ''), re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError as e:
                raise ValueError(f"结构化输出的JSON格式无效: {e}")
        return None