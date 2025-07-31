import logging
import json
import datetime
import sys

class Logger:
    def __init__(self, log_file='amaya_log.jsonl'):
        self.logger = logging.getLogger('amaya_event_logger')
        self.logger.setLevel(logging.INFO)
        self.logger.propagate = False

        # 如果已经有处理器，则清空，避免重复记录
        if self.logger.hasHandlers():
            self.logger.handlers.clear()

        # 1. 文件处理器 (JSONL 格式)
        file_handler = logging.FileHandler(log_file, mode='a', encoding='utf-8')
        file_formatter = logging.Formatter('%(message)s')
        file_handler.setFormatter(file_formatter)
        self.logger.addHandler(file_handler)

        # 2. 控制台处理器 (可读格式)
        console_handler = logging.StreamHandler(sys.stdout)
        # 使用自定义格式化器，使控制台输出更易读
        console_formatter = logging.Formatter('[%(asctime)s] [%(levelname)s] [%(event_type)s] - %(event_message)s', datefmt='%Y-%m-%d %H:%M:%S')
        
        # 为了实现自定义格式，我们使用一个Filter来注入额外字段
        class ContextFilter(logging.Filter):
            def filter(self, record):
                record.event_type = getattr(record, 'event_type', 'N/A')
                record.event_message = getattr(record, 'event_message', record.getMessage())
                return True
        
        self.logger.addFilter(ContextFilter())
        console_handler.setFormatter(console_formatter)
        self.logger.addHandler(console_handler)


    def log_event(self, event_type: str, data: dict):
        """
        将一个结构化的事件记录到日志文件和控制台。

        Args:
            event_type: 事件的类型 (e.g., 'USER_INPUT', 'AMAYA_RESPONSE', 'LLM_CALL').
            data: 与事件相关的具体数据。
        """
        # 准备用于写入JSONL文件的完整日志条目
        log_entry = {
            "timestamp": datetime.datetime.now().isoformat(),
            "type": event_type,
            "data": data
        }
        try:
            log_message_json = json.dumps(log_entry, ensure_ascii=False, default=str)
            
            # 准备用于控制台输出的简化消息
            console_message = data.get('content', data.get('message', data.get('reason', str(data))))
            if isinstance(console_message, dict):
                console_message = json.dumps(console_message, ensure_ascii=False)


            # 使用 extra 字典将自定义字段传递给格式化器
            extra_info = {
                'event_type': event_type,
                'event_message': console_message
            }
            self.logger.info(log_message_json, extra=extra_info)

        except Exception as e:
            # 在此处的打印是最后的防线
            print(f"[日志记录错误] 无法记录事件 '{event_type}': {e}")

# 创建一个全局的logger实例供其他模块使用
event_logger = Logger()

def disable_console_logging():
    """禁用控制台日志记录。"""
    logger = logging.getLogger('amaya_event_logger')
    # 查找并移除 StreamHandler (控制台处理器)
    for handler in logger.handlers[:]:
        if isinstance(handler, logging.StreamHandler):
            logger.removeHandler(handler)
