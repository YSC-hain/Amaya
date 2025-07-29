import logging
import json

def setup_logger(log_file='amaya_log.jsonl'):
    """设置一个将JSON对象写入文件的日志记录器。"""
    logger = logging.getLogger('amaya_llm_logger')
    logger.setLevel(logging.INFO)
    logger.propagate = False

    if logger.hasHandlers():
        return logger

    handler = logging.FileHandler(log_file, mode='a', encoding='utf-8')
    formatter = logging.Formatter('%(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger

llm_logger = setup_logger()

def log_llm_interaction(payload: dict, response: dict | str | None, error: str | None = None):
    """将LLM调用的请求、响应和任何错误作为一个JSON对象记录下来。"""
    log_entry = {
        "request": payload,
        "response": response,
        "error": error
    }
    try:
        # ensure_ascii=False 确保中文字符能被正确记录
        log_message = json.dumps(log_entry, ensure_ascii=False, default=str)
        llm_logger.info(log_message)
    except Exception as e:
        print(f"[日志记录错误] 无法记录LLM交互: {e}")
