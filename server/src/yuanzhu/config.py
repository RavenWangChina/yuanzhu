from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """应用配置（配置驱动形态切换：standalone | server | edge）"""

    database_url: str = "sqlite+aiosqlite:///./yuanzhu.db"
    mcp_endpoint: str = "/mcp"
    mode: str = "standalone"
    debug: bool = False
    base_url: str = "http://127.0.0.1:8600"   # CLI 连中控

    # 企微对话学习（管理员在企微后台自助配置后填入 .env）
    wecom_token: str = ""          # 回调验签 token
    wecom_aes_key: str = ""        # 回调加密 key（配置后启用验签通道）
    wecom_corp_id: str = ""
    wecom_allowed_chats: str = ""  # 授权群白名单，逗号分隔 chat_id；空=全收

    model_config = {
        "env_prefix": "YUANZHU_",
        "env_file": ".env",
    }


settings = Settings()
