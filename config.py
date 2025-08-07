import os

# -- OneBot V11 配置 --
# 你的 OneBot 实现 (如 NapCat) 的正向 WebSocket API 地址
# 这是我们的适配器需要连接的目标地址
ONEBOT_WS_URL = os.getenv("ONEBOT_WS_URL", "ws://127.0.0.1:3081")

# OneBot 的访问令牌 (Access Token)，如果你的 OneBot 配置了此项
# 则需要在这里填写，否则留空
ONEBOT_ACCESS_TOKEN = os.getenv("ONEBOT_ACCESS_TOKEN", "")


# -- 用户配置 --
# 在启动时，如果用户没有输入ID，将使用此默认ID
DEFAULT_USER_ID = os.getenv("DEFAULT_USER_ID", "user_default")

# -- Gemini API 配置 (用于 google-generativeai SDK) --
# 第三方服务提供的 API 端点 (不含版本路径)
# SDK 会自动附加 /v1beta 等路径
API_ENDPOINT = os.getenv("GEMINI_API_ENDPOINT", "yunwu.ai")

# 模型 ID
MODEL_ID = os.getenv("GEMINI_MODEL_ID", "gemini-2.5-pro-preview-06-05")

# API 密钥 - 从环境变量读取，提高安全性
# 请设置环境变量 GEMINI_API_KEY
API_KEY = os.getenv("GEMINI_API_KEY")
if not API_KEY:
    print("[警告] 未找到 GEMINI_API_KEY 环境变量，请设置后重新运行")
    print("请使用: export GEMINI_API_KEY='your_api_key' (或在Windows上使用 set 命令)")

# -- 记忆配置 --
# 短期记忆的最大Token限制
SHORT_TERM_MEMORY_TOKEN_LIMIT = int(os.getenv("SHORT_TERM_MEMORY_TOKEN_LIMIT", "2000"))

# 验证配置值
def validate_config():
    """验证配置参数的有效性。"""
    errors = []
    
    if not ONEBOT_WS_URL or not ONEBOT_WS_URL.strip():
        errors.append("ONEBOT_WS_URL 不能为空")
    elif not (ONEBOT_WS_URL.startswith('ws://') or ONEBOT_WS_URL.startswith('wss://')):
        errors.append("ONEBOT_WS_URL 必须以 ws:// 或 wss:// 开头")
    
    if not API_KEY:
        errors.append("必须设置 GEMINI_API_KEY 环境变量")
    
    if SHORT_TERM_MEMORY_TOKEN_LIMIT <= 0:
        errors.append("SHORT_TERM_MEMORY_TOKEN_LIMIT 必须大于 0")
    
    if errors:
        print("[错误] 配置验证失败:")
        for error in errors:
            print(f"  - {error}")
        return False
    
    return True

# 在模块加载时自动验证配置
if __name__ != "__main__":
    validate_config()