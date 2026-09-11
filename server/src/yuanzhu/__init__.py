"""元铸工坊 - 本体层与 MCP 服务"""

import os

# 启动提速：litellm 用本地价格表，禁远程拉取（曾致启动 10s+）
os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")

__version__ = "0.1.2"
