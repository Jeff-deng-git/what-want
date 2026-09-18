"""Provider Registry -- 6 个 OpenAI 兼容 LLM Provider 的元数据。

来源：chapter3/user-memory/config.py (PROVIDER_REGISTRY)
适配：env var 名 MINNIMAX（3 N's）匹配用户 Windows env。
"""
from typing import Optional

PROVIDER_REGISTRY = {
    "deepseek": {
        "label": "DS",
        "name": "DeepSeek",
        "env_key": "DEEPSEEK_API_KEY",
        "base_url": "https://api.deepseek.com/v1",
        "default_model": "deepseek-v4-pro",
        "test_model": "deepseek-v4-pro",
        "aliases": [],
    },
    "minimax": {
        "label": "MM",
        "name": "MiniMax",
        "env_key": "MINNIMAX_API_KEY",  # 3 N's -- match user's actual env var
        "base_url": "https://minnimax.chat/v1",
        "default_model": "MiniMax-M3",
        "test_model": "MiniMax-M3",
        "aliases": ["MiniMax"],
    },
    "kimi": {
        "label": "KM",
        "name": "Kimi",
        "env_key": "MOONSHOT_API_KEY",
        "base_url": "https://api.moonshot.cn/v1",
        "default_model": "kimi-k3",
        "test_model": "kimi-k3",
        "aliases": ["moonshot"],
    },
    "siliconflow": {
        "label": "SF",
        "name": "SiliconFlow",
        "env_key": "SILICONFLOW_API_KEY",
        "base_url": "https://api.siliconflow.cn/v1",
        "default_model": "Qwen/Qwen3-235B-A22B-Thinking-2507",
        "test_model": "Qwen/Qwen3-235B-A22B-Thinking-2507",
        "aliases": [],
    },
    "doubao": {
        "label": "DB",
        "name": "Doubao",
        "env_key": "DOUBAO_API_KEY",
        "base_url": "https://ark.cn-beijing.volces.com/api/v3",
        "default_model": "doubao-seed-1-6-thinking-250715",
        "test_model": "doubao-seed-1-6-thinking-250715",
        "aliases": [],
    },
    "openrouter": {
        "label": "OR",
        "name": "OpenRouter",
        "env_key": "OPENROUTER_API_KEY",
        "base_url": "https://openrouter.ai/api/v1",
        "default_model": "openai/gpt-5.6-luna",
        "test_model": "openai/gpt-5.6-luna",
        "aliases": [],
    },
}


def resolve_provider(provider: str) -> tuple[str, dict]:
    """规范化 provider 名（处理 alias） -> (canonical, meta)。"""
    p = (provider or "").lower()
    if p in PROVIDER_REGISTRY:
        return p, PROVIDER_REGISTRY[p]
    for canonical, meta in PROVIDER_REGISTRY.items():
        if p in [a.lower() for a in meta.get("aliases", [])]:
            return canonical, meta
    valid = ", ".join(PROVIDER_REGISTRY.keys())
    raise ValueError(f"Unsupported provider: {provider!r}. Use one of: {valid}")


def list_providers() -> list[dict]:
    """返回供前端展示的 provider 列表（不含 key）。"""
    return [
        {
            "id": canonical,
            "label": meta["label"],
            "name": meta["name"],
            "base_url": meta["base_url"],
            "default_model": meta["default_model"],
        }
        for canonical, meta in PROVIDER_REGISTRY.items()
    ]


def get_provider_meta(canonical: str) -> Optional[dict]:
    return PROVIDER_REGISTRY.get(canonical)