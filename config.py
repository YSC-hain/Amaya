# -- OneBot V11 配置 --
# 你的 OneBot 实现 (如 NapCat) 的正向 WebSocket API 地址
# 这是我们的适配器需要连接的目标地址
ONEBOT_WS_URL = "ws://127.0.0.1:3081"

# OneBot 的访问令牌 (Access Token)，如果你的 OneBot 配置了此项
# 则需要在这里填写，否则留空
ONEBOT_ACCESS_TOKEN = "j2WhKF1T9iRL"


# -- 用户配置 --
# 在启动时，如果用户没有输入ID，将使用此默认ID
DEFAULT_USER_ID = "user_default"

# -- Gemini API 配置 (用于 google-generativeai SDK) --
# 第三方服务提供的 API 端点 (不含版本路径)
# SDK 会自动附加 /v1beta 等路径
API_ENDPOINT = "yunwu.ai"

# 模型 ID
MODEL_ID = "gemini-2.5-pro-preview-06-05" # "gemini-2.5-flash-preview-05-20"

# 你的 API 密钥
# 重要: 请将 "your_secret_api_key" 替换为你的真实密钥
API_KEY = "sk-ANX3raYqcdssr2picqBBSZ9FaTvZdFpgaqIz2sgEFSN6Pe7e"

# -- 记忆配置 --
# 短期记忆的最大Token限制
SHORT_TERM_MEMORY_TOKEN_LIMIT = 2000