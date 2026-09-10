"""LiteLLM 代理薄层（多协议兼容转发 + 计量提取）

模型路由走 ProviderRegistry（2026-09-10 兼容性改造）：
dsh 配置导入（零配置复用 dsh 的 key）→ .env 自定义 → 内置兜底。
一切 OpenAI 兼容端点（天翼云/vLLM/Ollama/one-api）经 openai-completions 协议接入。
"""
import litellm

from yuanzhu.db.models import ModelUsage


async def acompletion(**kwargs):
    """转发到 litellm；失败原样抛出（降级兜底由调用方处理并附上下文）"""
    from yuanzhu.gateway.providers import get_registry
    try:
        resolved = get_registry().resolve(kwargs.get("model", ""))
        kwargs.update(resolved)
    except ValueError:
        raise  # 未知模型：带可用清单的报错直接上抛
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
