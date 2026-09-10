"""LiteLLM 代理薄层（OpenAI 兼容转发 + 计量提取）"""
import litellm

from yuanzhu.db.models import ModelUsage

# 裸模型名 → litellm provider 路由（v0.1 按名直路由，ADR-003；
# 供应商凭据走环境变量：DEEPSEEK_API_KEY 等 litellm 约定）
LITELLM_MODEL_MAP = {
    "deepseek-chat": "deepseek/deepseek-chat",
    "deepseek-reasoner": "deepseek/deepseek-reasoner",
    "qwen-plus": "dashscope/qwen-plus",
}


async def acompletion(**kwargs):
    """转发到 litellm；失败原样抛出（降级兜底由调用方处理并附上下文）"""
    model = kwargs.get("model", "")
    if model in LITELLM_MODEL_MAP:
        kwargs["model"] = LITELLM_MODEL_MAP[model]
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
    # ponytail: 估费 v0.1 记 0.0，接入 litellm completion_cost 需响应对象与价目表，挂账里程碑 6
    return ModelUsage(
        model=model,
        task_id=task_id,
        caller=caller,
        prompt_tokens=usage.get("prompt_tokens") or 0,
        completion_tokens=usage.get("completion_tokens") or 0,
        estimated_cost=0.0,
    )
