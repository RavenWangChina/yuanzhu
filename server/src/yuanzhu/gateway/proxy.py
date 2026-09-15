"""LiteLLM 代理薄层（多协议兼容转发 + 计量提取）

模型路由走 ProviderRegistry（2026-09-10 兼容性改造）：
dsh 配置导入（零配置复用 dsh 的 key）→ .env 自定义 → 内置兜底。
一切 OpenAI 兼容端点（天翼云/vLLM/Ollama/one-api）经 openai-completions 协议接入。
"""
from yuanzhu.db.models import ModelUsage

# 需要多协议路由（litellm）的模型前缀；其余 OpenAI 兼容端点走零依赖直连层
_LITELLM_PREFIXES = ("openai/", "anthropic/", "azure/", "bedrock/", "gemini/",
                     "vertex_ai/", "mistral/", "cohere/", "groq/")


def __getattr__(name):
    """PEP 562 懒加载：proxy.litellm 访问时才 import（未装环境顶层导入不炸；
    测试 monkeypatch 的锚点也由此提供）"""
    if name == "litellm":
        import litellm
        return litellm
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


async def _openai_direct(kwargs: dict) -> dict:
    """v0.2.0 零依赖直连：OpenAI 兼容端点（litellm 未装时的主路径）

    天翼云/vLLM/Ollama/one-api/DeepSeek/GLM 等 OpenAI 兼容端点全覆盖；
    返回 dict（与 litellm 响应在 extract_usage / engine.call_model 处同构兼容）。
    """
    import httpx
    model = kwargs["model"]
    for pfx in _LITELLM_PREFIXES:
        if model.startswith(pfx):
            model = model[len(pfx):]
            break
    base = str(kwargs.get("api_base", "")).rstrip("/")
    headers = {}
    if kwargs.get("api_key"):
        headers["Authorization"] = f"Bearer {kwargs['api_key']}"
    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post(f"{base}/chat/completions", headers=headers,
                              json={"model": model, "messages": kwargs.get("messages", [])})
        r.raise_for_status()
        return r.json()


async def acompletion(**kwargs):
    """模型调用路由（v0.2.0 双路径）：
    ① OpenAI 兼容端点（有 api_base、无特殊前缀）→ 零依赖直连
    ② 多协议模型（anthropic/azure/...）→ litellm（可选依赖，未装给安装提示）"""
    from yuanzhu.gateway.providers import get_registry
    try:
        resolved = get_registry().resolve(kwargs.get("model", ""))
        kwargs.update(resolved)
    except ValueError:
        raise  # 未知模型：带可用清单的报错直接上抛

    # v0.2.0 路由：显式配了 api_base = OpenAI 兼容端点（dsh 路由多为 openai/前缀+api_base，
    # 前缀只是 litellm 协议标记，直连层负责剥）→ 直连；否则交 litellm 自有端点路由
    if kwargs.get("api_base"):
        return await _openai_direct(kwargs)

    model = kwargs.get("model", "")
    try:
        import litellm
    except ImportError:
        raise ValueError(
            f"模型 {model!r} 需要多协议网关支持。安装：pip install yuanzhu[gateway]；"
            f"或为该模型配置 OpenAI 兼容端点（api_base）后走内置直连。")
    return await litellm.acompletion(**kwargs)


def extract_usage(response) -> dict:
    """从 litellm 响应提取 usage（ModelResponse 或 dict）"""
    if hasattr(response, "usage") and response.usage is not None:
        u = response.usage
        if hasattr(u, "model_dump"):
            u = u.model_dump()
        return {
            "prompt_tokens": getattr(u, "prompt_tokens", None) or u.get("prompt_tokens", 0),
            "completion_tokens": getattr(u, "completion_tokens", None) or u.get("completion_tokens", 0),
        }
    data = response if isinstance(response, dict) else response.model_dump()
    u = data.get("usage") or {}
    return {
        "prompt_tokens": u.get("prompt_tokens", 0),
        "completion_tokens": u.get("completion_tokens", 0),
    }


def build_usage_record(model: str, usage: dict, task_id, caller: str) -> ModelUsage:
    """计量记录（估费：v0.1 用 litellm 的成本计算，不可得时记 0）"""
    # v0.1.1 估费（审查 C2 修正版）：
    # ①自定义价目表 YUANZHU_MODEL_PRICES（JSON：模型→{"in":元/token,"out":...}）优先
    #   ——glm 等网关模型不在 litellm 价目内，运维按实际价格配置
    # ②fallback litellm 本地价目表；③无价/异常记 0（不炸）
    cost = 0.0
    try:
        custom = _custom_prices()
        if model in custom:
            cost = (custom[model].get("in", 0) * (usage.get("prompt_tokens") or 0)
                    + custom[model].get("out", 0) * (usage.get("completion_tokens") or 0))
        else:
            try:
                import litellm
            except ImportError:
                litellm = None
            if litellm is None:
                cost = 0.0
            else:
                cost = float(litellm.model_cost.get(model, {}).get("input_cost_per_token", 0)
                         * (usage.get("prompt_tokens") or 0)
                         + litellm.model_cost.get(model, {}).get("output_cost_per_token", 0)
                         * (usage.get("completion_tokens") or 0)) or 0.0
    except Exception:
        cost = 0.0
    return ModelUsage(
        model=model,
        task_id=task_id,
        caller=caller,
        prompt_tokens=usage.get("prompt_tokens") or 0,
        completion_tokens=usage.get("completion_tokens") or 0,
        estimated_cost=cost,
    )


def _custom_prices() -> dict:
    """读 YUANZHU_MODEL_PRICES 环境变量（JSON，如 {"glm-5.1": {"in": 1e-6, "out": 3e-6}}）"""
    import json
    import os
    raw = os.environ.get("YUANZHU_MODEL_PRICES", "")
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except Exception:
        return {}
