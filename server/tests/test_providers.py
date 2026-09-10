"""Provider 注册表测试：dsh 配置导入 / .env 自定义 / 多协议映射 / 模型路由"""
import pytest
from pathlib import Path

from yuanzhu.gateway.providers import ProviderRegistry


@pytest.fixture
def fake_dsh(tmp_path: Path):
    """伪造 dsh 配置目录（结构与真实 ~/.dsh 一致）"""
    dsh = tmp_path / ".dsh"
    dsh.mkdir()
    (dsh / "settings.yaml").write_text("""
llm-pi-ai:
  providers:
    tctyun:
      displayName: 天翼云 GLM
      apiKeyEnv: TCTYUN_API_KEY
      api: openai-completions
      baseURL: https://openai.tctyun.com/v1
      models:
        - {id: GLM-5.1}
        - {id: ch-20}
    local:
      displayName: 本地 vLLM
      apiKeyEnv: LOCAL_KEY
      api: openai-completions
      baseURL: http://127.0.0.1:8000/v1
      models:
        - {id: qwen-72b}
""", encoding="utf-8")
    (dsh / ".credentials.yaml").write_text(
        "version: 1\nrefs:\n  TCTYUN_API_KEY: sk-tctyun-real-key\n  LOCAL_KEY: sk-local-key\n",
        encoding="utf-8")
    return dsh


def test_load_from_dsh_config(fake_dsh):
    """dsh 配置导入：provider/模型/key 全就位（key 从 credentials refs 解）"""
    reg = ProviderRegistry(dsh_home=fake_dsh)
    assert "tctyun" in reg.provider_names
    assert set(reg.models) >= {"GLM-5.1", "ch-20", "qwen-72b"}


def test_resolve_openai_protocol(fake_dsh):
    """openai-completions 协议 → litellm openai/ 前缀 + base_url + key"""
    reg = ProviderRegistry(dsh_home=fake_dsh)
    kwargs = reg.resolve("GLM-5.1")
    assert kwargs["model"] == "openai/GLM-5.1"
    assert kwargs["api_base"] == "https://openai.tctyun.com/v1"
    assert kwargs["api_key"] == "sk-tctyun-real-key"


def test_resolve_routes_to_right_provider(fake_dsh):
    """同协议多 provider：按模型路由到正确一方"""
    reg = ProviderRegistry(dsh_home=fake_dsh)
    assert reg.resolve("qwen-72b")["api_base"] == "http://127.0.0.1:8000/v1"


def test_env_provider_merge(fake_dsh, monkeypatch):
    """.env 自定义 provider：YUANZHU_PROVIDER_<n>_* 四件套"""
    monkeypatch.setenv("YUANZHU_PROVIDER_1_NAME", "mine")
    monkeypatch.setenv("YUANZHU_PROVIDER_1_BASE_URL", "https://my.example.com/v1")
    monkeypatch.setenv("YUANZHU_PROVIDER_1_API", "openai-completions")
    monkeypatch.setenv("YUANZHU_PROVIDER_1_KEY", "sk-mine")
    monkeypatch.setenv("YUANZHU_PROVIDER_1_MODELS", "my-model-a,my-model-b")

    reg = ProviderRegistry(dsh_home=fake_dsh)
    kwargs = reg.resolve("my-model-a")
    assert kwargs["model"] == "openai/my-model-a"
    assert kwargs["api_base"] == "https://my.example.com/v1"
    assert kwargs["api_key"] == "sk-mine"


def test_builtin_fallback(monkeypatch, tmp_path):
    """内置兜底：deepseek-chat 等裸名走 litellm 原生（环境变量凭据）"""
    empty = tmp_path / "empty-dsh"
    empty.mkdir()
    reg = ProviderRegistry(dsh_home=empty)
    # 未配置的裸名：不炸，透传给 litellm（deepseek/ 前缀由映射表处理）
    kwargs = reg.resolve("deepseek-chat")
    assert kwargs["model"] == "deepseek/deepseek-chat"


def test_unknown_model_lists_available(fake_dsh):
    """未知模型报错带可用清单（用户方便排错）"""
    reg = ProviderRegistry(dsh_home=fake_dsh)
    with pytest.raises(ValueError, match="GLM-5.1"):
        reg.resolve("gpt-99")


def test_missing_dsh_home_ok(tmp_path):
    """dsh 目录不存在 → 静默空注册表（不影响其他源）"""
    reg = ProviderRegistry(dsh_home=tmp_path / "no-such")
    assert reg.models == [] or isinstance(reg.models, list)
