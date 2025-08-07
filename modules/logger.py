import logging
import json
import datetime
import sys
import os
from logging.handlers import RotatingFileHandler

class Logger:
    def __init__(self, log_file='amaya_log.jsonl', max_size=10*1024*1024, backup_count=5):
        """初始化日志记录器，包含日志轮转功能。
        
        Args:
            log_file: 日志文件路径
            max_size: 单个日志文件的最大大小（字节），默认10MB
            backup_count: 保留的备份日志文件数量
        """
        # 验证日志文件路径
        if not isinstance(log_file, str) or not log_file.strip():
            raise ValueError("Log file path must be a non-empty string")
        
        # 确保日志目录存在
        log_dir = os.path.dirname(os.path.abspath(log_file))
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)
        
        self.logger = logging.getLogger('amaya_event_logger')
        self.logger.setLevel(logging.INFO)
        self.logger.propagate = False

        # 如果已经有处理器，则清空，避免重复记录
        if self.logger.hasHandlers():
            self.logger.handlers.clear()

        # 1. 文件处理器 (JSONL 格式) - 使用轮转文件处理器
        try:
            file_handler = RotatingFileHandler(
                log_file, 
                mode='a', 
                maxBytes=max_size, 
                backupCount=backup_count,
                encoding='utf-8'
            )
            file_formatter = logging.Formatter('%(message)s')
            file_handler.setFormatter(file_formatter)
            self.logger.addHandler(file_handler)
        except (OSError, IOError) as e:
            print(f"[警告] 无法创建日志文件处理器: {e}")
            # 继续执行，但不会有文件日志

        # 2. 控制台处理器 (可读格式)
        try:
            console_handler = logging.StreamHandler(sys.stdout)
            # 使用自定义格式化器，使控制台输出更易读
            console_formatter = logging.Formatter(
                '[%(asctime)s] [%(levelname)s] [%(event_type)s] - %(event_message)s', 
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            
            # 为了实现自定义格式，我们使用一个Filter来注入额外字段
            class ContextFilter(logging.Filter):
                def filter(self, record):
                    record.event_type = getattr(record, 'event_type', 'N/A')
                    record.event_message = getattr(record, 'event_message', record.getMessage())
                    return True
            
            # 只为控制台处理器添加过滤器
            console_handler.addFilter(ContextFilter())
            console_handler.setFormatter(console_formatter)
            self.logger.addHandler(console_handler)
        except Exception as e:
            print(f"[警告] 无法创建控制台处理器: {e}")


    def log_event(self, event_type: str, data: dict):
        """
        将一个结构化的事件记录到日志文件和控制台。
        包含输入验证和错误处理。

        Args:
            event_type: 事件的类型 (e.g., 'USER_INPUT', 'AMAYA_RESPONSE', 'LLM_CALL').
            data: 与事件相关的具体数据。
        """
        # 输入验证
        if not isinstance(event_type, str) or not event_type.strip():
            print("[日志记录错误] event_type 必须是非空字符串")
            return
            
        if not isinstance(data, dict):
            print(f"[日志记录错误] data 必须是字典类型，收到: {type(data)}")
            return
        
        event_type = event_type.strip()
        
        # 准备用于写入JSONL文件的完整日志条目
        log_entry = {
            "timestamp": datetime.datetime.now().isoformat(),
            "type": event_type,
            "data": data
        }
        
        try:
            # 限制日志条目大小，防止内存问题
            log_message_json = json.dumps(log_entry, ensure_ascii=False, default=str)
            if len(log_message_json) > 100000:  # 100KB 限制
                # 截断数据
                truncated_data = {"error": "Data too large, truncated", "original_size": len(log_message_json)}
                log_entry["data"] = truncated_data
                log_message_json = json.dumps(log_entry, ensure_ascii=False, default=str)
            
            # 准备用于控制台输出的简化消息
            console_message = data.get('content', data.get('message', data.get('reason', str(data))))
            if isinstance(console_message, dict):
                console_message = json.dumps(console_message, ensure_ascii=False)
            elif isinstance(console_message, str) and len(console_message) > 1000:
                console_message = console_message[:1000] + "...[truncated]"

            # 使用 extra 字典将自定义字段传递给格式化器
            extra_info = {
                'event_type': event_type,
                'event_message': console_message
            }
            self.logger.info(log_message_json, extra=extra_info)

        except (TypeError, ValueError) as e:
            # JSON 序列化错误
            print(f"[日志记录错误] JSON 序列化失败 '{event_type}': {e}")
        except Exception as e:
            # 其他错误
            print(f"[日志记录错误] 无法记录事件 '{event_type}': {e}")

# 创建一个全局的logger实例供其他模块使用
event_logger = Logger()

def disable_console_logging():
    """禁用控制台日志记录，包含错误处理。"""
    try:
        logger = logging.getLogger('amaya_event_logger')
        # 查找并移除 StreamHandler (控制台处理器)
        handlers_to_remove = []
        for handler in logger.handlers:
            if isinstance(handler, logging.StreamHandler) and handler.stream == sys.stdout:
                handlers_to_remove.append(handler)
        
        for handler in handlers_to_remove:
            logger.removeHandler(handler)
            handler.close()  # 正确关闭处理器
            
        if handlers_to_remove:
            print("[信息] 控制台日志记录已禁用")
    except Exception as e:
        print(f"[警告] 禁用控制台日志时出错: {e}")
