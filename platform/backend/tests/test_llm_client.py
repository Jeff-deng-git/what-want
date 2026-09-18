"""llm_client must source provider metadata from app.security.providers only."""
import asyncio
import pytest
from types import SimpleNamespace
from app.security.providers import PROVIDER_REGISTRY


def test_provider_metadata_matches_security_registry():
    """No two-source-of-truth: llm_client must use security/providers.py."""
    from app.services.llm_client import _get_base_url
    for canonical, meta in PROVIDER_REGISTRY.items():
        assert _get_base_url(canonical) == meta["base_url"], (
            f"provider {canonical!r}: llm_client={_get_base_url(canonical)!r} "
            f"vs security={meta['base_url']!r}"
        )


def test_legacy_providers_dict_removed():
    """llm_client.PROVIDERS must be gone — single registry only."""
    from app.services import llm_client
    assert not hasattr(llm_client, "PROVIDERS"), (
        "llm_client.PROVIDERS still defined; rerun failed to clean up duplicate source"
    )


def test_get_base_url_rejects_unknown_provider():
    from app.services.llm_client import _get_base_url
    with pytest.raises(ValueError, match="Unsupported provider"):
        _get_base_url("not-a-real-provider")


@pytest.mark.asyncio
async def test_call_llm_rejects_empty_content(monkeypatch):
    from app.services import llm_client

    class FakeCompletions:
        async def create(self, **kwargs):
            return SimpleNamespace(
                choices=[SimpleNamespace(
                    message=SimpleNamespace(content="", reasoning_content="internal"),
                    finish_reason="stop",
                )]
            )

    class FakeClient:
        def __init__(self, **kwargs):
            self.chat = SimpleNamespace(completions=FakeCompletions())

    monkeypatch.setattr(llm_client, "AsyncOpenAI", FakeClient)
    with pytest.raises(llm_client.LLMEmptyResponseError, match="empty response"):
        await llm_client.call_llm(
            provider="deepseek",
            model="deepseek-chat",
            api_key="fake",
            system="system",
            user="user",
        )

@pytest.mark.asyncio
async def test_call_llm_retries_after_reasoning_length(monkeypatch):
    from app.services import llm_client

    requests = []

    class FakeCompletions:
        async def create(self, **kwargs):
            requests.append(kwargs)
            if len(requests) == 1:
                return SimpleNamespace(
                    choices=[SimpleNamespace(
                        message=SimpleNamespace(content="", reasoning_content="internal"),
                        finish_reason="length",
                    )]
                )
            return SimpleNamespace(
                choices=[SimpleNamespace(
                    message=SimpleNamespace(content='{"ok": true}'),
                    finish_reason="stop",
                )]
            )

    class FakeClient:
        def __init__(self, **kwargs):
            self.chat = SimpleNamespace(completions=FakeCompletions())

    monkeypatch.setattr(llm_client, "AsyncOpenAI", FakeClient)
    result = await llm_client.call_llm(
        provider="deepseek",
        model="deepseek-v4-flash",
        api_key="fake",
        system="system",
        user="user",
        max_tokens=1500,
        json_mode=True,
    )
    assert result == '{"ok": true}'
    assert len(requests) == 2
    assert requests[0]["max_tokens"] == 1500
    assert requests[1]["max_tokens"] == 4000
    assert requests[1]["response_format"] == {"type": "json_object"}


@pytest.mark.asyncio
async def test_call_llm_can_explicitly_enable_provider_thinking(monkeypatch):
    from app.services import llm_client

    requests = []

    class FakeCompletions:
        async def create(self, **kwargs):
            requests.append(kwargs)
            return SimpleNamespace(
                choices=[SimpleNamespace(
                    message=SimpleNamespace(content='{"ok": true}'),
                    finish_reason="stop",
                )]
            )

    class FakeClient:
        def __init__(self, **kwargs):
            self.chat = SimpleNamespace(completions=FakeCompletions())

    monkeypatch.setattr(llm_client, "AsyncOpenAI", FakeClient)
    await llm_client.call_llm(
        provider="deepseek",
        model="deepseek-v4-flash",
        api_key="fake",
        system="system",
        user="user",
        json_mode=True,
        thinking_mode="enabled",
    )

    assert requests[0]["extra_body"] == {"thinking": {"type": "enabled"}}


@pytest.mark.asyncio
async def test_call_llm_disables_sdk_retries_by_default(monkeypatch):
    from app.services import llm_client

    init_kwargs = {}

    class FakeCompletions:
        async def create(self, **kwargs):
            return SimpleNamespace(
                choices=[SimpleNamespace(
                    message=SimpleNamespace(content="ok"),
                    finish_reason="stop",
                )]
            )

    class FakeClient:
        def __init__(self, **kwargs):
            init_kwargs.update(kwargs)
            self.chat = SimpleNamespace(completions=FakeCompletions())

    monkeypatch.setattr(llm_client, "AsyncOpenAI", FakeClient)
    result = await llm_client.call_llm(
        provider="deepseek",
        model="deepseek-v4-flash",
        api_key="fake",
        system="system",
        user="user",
        timeout=120.0,
    )

    assert result == "ok"
    assert init_kwargs["timeout"] == 120.0
    assert init_kwargs["max_retries"] == 0
@pytest.mark.asyncio
async def test_call_llm_enforces_total_timeout_across_attempts(monkeypatch):
    from app.services import llm_client

    requests = []

    class FakeCompletions:
        async def create(self, **kwargs):
            requests.append(kwargs)
            await asyncio.sleep(0.05)

    class FakeClient:
        def __init__(self, **kwargs):
            self.chat = SimpleNamespace(completions=FakeCompletions())

    monkeypatch.setattr(llm_client, "AsyncOpenAI", FakeClient)
    with pytest.raises(llm_client.LLMTimeoutError, match="total"):
        await llm_client.call_llm(
            provider="deepseek",
            model="deepseek-v4-flash",
            api_key="fake",
            system="system",
            user="user",
            timeout=0.01,
        )
    assert len(requests) == 1
