import re
import json
import os

class PromptManager:
    """负责读取、解析和渲染 prompt.md 模板文件，包含安全验证。"""
    def __init__(self, file_path='prompt.md'):
        # 验证文件路径安全性
        if not isinstance(file_path, str) or not file_path.strip():
            raise ValueError("File path must be a non-empty string")
        
        # 防止路径遍历攻击
        file_path = file_path.strip()
        if '..' in file_path or file_path.startswith('/'):
            raise ValueError("Invalid file path: potential directory traversal")
        
        # 限制只能访问 .md 文件
        if not file_path.endswith('.md'):
            raise ValueError("Only .md files are allowed")
            
        self.file_path = file_path
        self.templates = self._load_and_parse()

    def _load_and_parse(self):
        """加载并解析prompt.md文件，将其分割成不同的部分。"""
        templates = {}
        try:
            # 检查文件是否存在
            if not os.path.exists(self.file_path):
                raise FileNotFoundError(f"错误: 提示词文件未找到于 '{self.file_path}'")
            
            # 检查文件大小，防止读取过大文件
            file_size = os.path.getsize(self.file_path)
            if file_size > 10 * 1024 * 1024:  # 10MB 限制
                raise ValueError(f"文件过大: {file_size} bytes > 10MB")
                
            with open(self.file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            parts = content.split('---')

            if len(parts) > 0:
                templates['system_prompt'] = self._extract_section(parts[0], "System Prompt")

            if len(parts) > 1:
                templates['dynamic_prompt'] = self._extract_section(parts[1], "Dynamic System Prompt")

            if len(parts) > 2:
                templates['structured_output'] = self._extract_section(parts[2], "Structured Output Json")

        except FileNotFoundError as e:
            raise e  # 保持原异常信息
        except Exception as e:
            raise RuntimeError(f"解析提示词文件时出错: {e}") from e  # 使用 from e 保持异常链

        return templates

    def _extract_section(self, part_content, section_name):
        """从文本块中提取指定部分的内容。"""
        header = f"# {section_name}"
        content = part_content.replace(header, '', 1).strip()
        return content

    def render_system_prompt(self, variables: dict):
        """渲染系统提示，并替换其中的占位符，包含输入验证。"""
        if not isinstance(variables, dict):
            raise TypeError("Variables must be a dictionary")
            
        template = self.templates.get('system_prompt', '')
        if not template:
            print("[警告] 系统提示模板为空")
            return ''
            
        for key, value in variables.items():
            if not isinstance(key, str):
                print(f"[警告] 变量名必须是字符串: {type(key)}")
                continue
            # 限制替换的值的长度，防止内存问题
            str_value = str(value)
            if len(str_value) > 100000:  # 100KB 限制
                str_value = str_value[:100000] + "...[truncated]"
            template = template.replace(f"{{{{{key}}}}}", str_value)
        return template

    def get_json_schema(self):
        """获取结构化输出的JSON Schema定义，使用更安全的正则表达式。"""
        structured_output = self.templates.get('structured_output', '')
        if not structured_output:
            print("[警告] 结构化输出模板为空")
            return None
            
        # 使用更精确的正则表达式，防止 ReDoS 攻击
        pattern = r'```structured_output_json\s*\n([\s\S]*?)\n```'
        match = re.search(pattern, structured_output)
        if match:
            try:
                json_str = match.group(1).strip()
                # 限制 JSON 字符串长度
                if len(json_str) > 50000:  # 50KB 限制
                    raise ValueError("结构化输出 JSON 过大")
                return json.loads(json_str)
            except json.JSONDecodeError as e:
                raise ValueError(f"结构化输出的JSON格式无效: {e}") from e
        else:
            print("[警告] 未找到结构化输出 JSON 代码块")
        return None