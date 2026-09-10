from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """应用配置（配置驱动形态切换：standalone | server | edge）"""

    database_url: str = "sqlite+aiosqlite:///./yuanzhu.db"
    mcp_endpoint: str = "/mcp"
    mode: str = "standalone"
    debug: bool = False

    model_config = {
        "env_prefix": "YUANZHU_",
        "env_file": ".env",
    }


settings = Settings()
