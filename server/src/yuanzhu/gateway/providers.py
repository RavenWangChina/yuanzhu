"""Provider 注册表：多协议模型接入的统一路由（多协议兼容改造，2026-09-10）

三层配置源（先到先得）：
1. dsh 配置导入（~/.dsh/settings.yaml 的 llm-pi-ai.providers +
   .credentials.yaml 的 refs 解 key）——dsh 用户零配置复用
2. .env 自定义（YUANZHU_PROVIDER_<n>_{NAME,BASE_URL,API,KEY,MODELS}）
3. 内置兜底（LITELLM_MODEL_MAP：deepseek 等裸名走 litellm 原生）

协议映射（providers[].api 字段，与 dsh 语义对齐）：
- openai-completions → litellm openai/<model> + api_base + api_key
  （一切 OpenAI 兼容端点：天翼云/vLLM/Ollama/DeepSeek 自建/one-api…）
- anthropic-messages → litellm anthropic/<model>（预留）
"""
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

# 内置兜底：裸模型名 → litellm provider 前缀（凭据走环境变量，litellm 约定）
BUILTIN_MAP = {
    "deepseek-chat": "deepseek/deepseek-chat",
    "deepseek-reasoner": "deepseek/deepseek-reasoner",
    "qwen-plus": "dashscope/qwen-plus",
}

DEFAULT_DSH_HOME = Path.home() / ".dsh"

# api 类型 → litellm 前缀
API_PREFIX = {
    "openai-completions": "openai/",
    "anthropic-messages": "anthropic/",
}


class ProviderRegistry:
    def __init__(self, dsh_home: Optional[Path] = None):
        self.dsh_home = Path(dsh_home) if dsh_home else DEFAULT_DSH_HOME
        self._routes: Dict[str, Dict[str, Any]] = {}  # model_id -> litellm kwargs
        self._names: List[str] = []
        self._load_dsh()
        self._load_env()
        self._load_builtin()

    # ---------- 加载 ----------

    def _load_dsh(self):
        """导入 dsh 配置（providers + credentials refs 解 key）"""
        settings = self.dsh_home / "settings.yaml"
        creds_file = self.dsh_home / ".credentials.yaml"
        if not settings.is_file():
            return

        refs: Dict[str, str] = {}
        if creds_file.is_file():
            try:
                creds = yaml.safe_load(creds_file.read_text(encoding="utf-8")) or {}
                refs = creds.get("refs") or {}
            except Exception:
                refs = {}

        data = yaml.safe_load(settings.read_text(encoding="utf-8")) or {}
        providers = ((data.get("llm-pi-ai") or {}).get("providers")) or {}
        for name, p in providers.items():
            base = p.get("baseURL")
            api = p.get("api", "openai-completions")
            prefix = API_PREFIX.get(api)
            if not base or not prefix:
                continue
            key = refs.get(p.get("apiKeyEnv", "")) or os.environ.get(p.get("apiKeyEnv", ""), "")
            for m in p.get("models") or []:
                model_id = m.get("id") if isinstance(m, dict) else m
                if model_id:
                    self._routes[str(model_id)] = {
                        "model": prefix + str(model_id),
                        "api_base": base,
                        "api_key": key,
                        "_provider": name,
                    }
                    self._names.append(name)

    def _load_env(self):
        """.env 自定义 provider：YUANZHU_PROVIDER_<n>_{NAME,BASE_URL,API,KEY,MODELS}"""
        n = 1
        while os.environ.get(f"YUANZHU_PROVIDER_{n}_BASE_URL"):
            prefix_env = f"YUANZHU_PROVIDER_{n}_"
            base = os.environ[prefix_env + "BASE_URL"]
            api = os.environ.get(prefix_env + "API", "openai-completions")
            key = os.environ.get(prefix_env + "KEY", "")
            models = [m.strip() for m in os.environ.get(prefix_env + "MODELS", "").split(",") if m.strip()]
            litellm_prefix = API_PREFIX.get(api, "openai/")
            name = os.environ.get(prefix_env + "NAME", f"env-{n}")
            for model_id in models:
                self._routes[model_id] = {
                    "model": litellm_prefix + model_id,
                    "api_base": base,
                    "api_key": key,
                    "_provider": name,
                }
                self._names.append(name)
            n += 1

    def _load_builtin(self):
        """内置兜底（用户未配的裸名）"""
        for bare, mapped in BUILTIN_MAP.items():
            self._routes.setdefault(bare, {"model": mapped})

    # ---------- 查询 ----------

    @property
    def provider_names(self) -> List[str]:
        return sorted(set(self._names))

    @property
    def models(self) -> List[str]:
        return sorted(self._routes.keys())

    def resolve(self, model: str) -> Dict[str, Any]:
        """模型名 → litellm 调用参数（未配置的裸名原样透传，litellm 自行路由）"""
        if model in self._routes:
            return {k: v for k, v in self._routes[model].items() if not k.startswith("_")}
        if model in BUILTIN_MAP:
            return {"model": BUILTIN_MAP[model]}
        # 透传前给出排错信息面：可配但没配的才报错；litellm 认识的（如 claude-xxx）放行
        known_native = any(model.startswith(p) for p in ("openai/", "anthropic/", "deepseek/", "dashscope/"))
        if known_native or ":" in model:
            return {"model": model}
        raise ValueError(
            f"未知模型 {model!r}，可用：{', '.join(self.models[:20])}"
            f"（或配置 YUANZHU_PROVIDER_n_* / dsh providers 接入）"
        )


# 进程级单例（配置文件启动时读一次）
_registry: Optional[ProviderRegistry] = None


def get_registry() -> ProviderRegistry:
    global _registry
    if _registry is None:
        _registry = ProviderRegistry()
    return _registry
