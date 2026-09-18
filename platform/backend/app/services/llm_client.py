"""LLM client -- single provider source: app.security.providers.PROVIDER_REGISTRY."""
import asyncio
import json
import logging
import os
from time import monotonic
from openai import APIConnectionError, APIError, APITimeoutError, AsyncOpenAI, RateLimitError
from cryptography.fernet import Fernet
from pathlib import Path

from app.security.providers import resolve_provider

logger = logging.getLogger(__name__)


class LLMEmptyResponseError(RuntimeError):
    """The provider returned a completion without usable answer content."""


class LLMTimeoutError(RuntimeError):
    """The provider did not answer within the configured request timeout."""


def _content_to_text(content):
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    parts = []
    for item in content:
        if isinstance(item, str):
            parts.append(item)
        elif isinstance(item, dict):
            text = item.get("text")
            if isinstance(text, str):
                parts.append(text)
        else:
            text = getattr(item, "text", None)
            if isinstance(text, str):
                parts.append(text)
    return "".join(parts)


# Encryption key from file (created on first run if missing)
KEY_FILE = Path(__file__).parent.parent / "data" / "secret.key"


def _get_fernet():
    if not KEY_FILE.exists():
        KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
        key = Fernet.generate_key()
        KEY_FILE.write_bytes(key)
    return Fernet(KEY_FILE.read_bytes())


def encrypt_key(plaintext: str) -> str:
    return _get_fernet().encrypt(plaintext.encode()).decode()


def decrypt_key(ciphertext: str) -> str:
    return _get_fernet().decrypt(ciphertext.encode()).decode()


def _get_base_url(provider: str) -> str:
    """Single source of truth lives in app.security.providers."""
    _, meta = resolve_provider(provider)
    return meta["base_url"]


async def call_llm(provider: str, model: str, api_key: str, system: str, user: str,
                    temperature: float = 0.7, max_tokens: int = 2000,
                    json_mode: bool = False, timeout: float = 30.0, max_retries: int = 0,
                    reasoning_retry: bool = True, thinking_mode: str | None = None) -> str:
    """Call LLM via OpenAI-compatible API. Returns raw text response.

    timeout: total seconds allowed across all provider attempts (default 30s).
    max_retries: SDK-level retries for this request; defaults to zero because LLM POSTs are not idempotent.
    """
    base_url = _get_base_url(provider)

    client = AsyncOpenAI(api_key=api_key, base_url=base_url, timeout=timeout, max_retries=max_retries)
    kwargs = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    if thinking_mode:
        if thinking_mode not in {"enabled", "disabled"}:
            raise ValueError("thinking_mode must be 'enabled' or 'disabled'")
        kwargs["extra_body"] = {"thinking": {"type": thinking_mode}}

    deadline = monotonic() + timeout
    for attempt in range(2 if reasoning_retry else 1):
        request_kwargs = dict(kwargs)
        if attempt:
            request_kwargs["max_tokens"] = min(max(max_tokens * 2, 4000), 6000)
        remaining = deadline - monotonic()
        if remaining <= 0:
            raise LLMTimeoutError(f"LLM provider timed out after {timeout:g}s total")
        try:
            response = await asyncio.wait_for(
                client.chat.completions.create(**request_kwargs),
                timeout=remaining,
            )
        except (APITimeoutError, asyncio.TimeoutError) as exc:
            raise LLMTimeoutError(f"LLM provider timed out after {timeout:g}s total") from exc
        choices = getattr(response, "choices", None) or []
        if not choices:
            raise LLMEmptyResponseError("LLM returned no choices")
        choice = choices[0]
        message = getattr(choice, "message", None)
        content = _content_to_text(getattr(message, "content", None))
        finish_reason = getattr(choice, "finish_reason", None)
        has_reasoning = bool(getattr(message, "reasoning_content", None))
        if content.strip():
            return content
        if reasoning_retry and attempt == 0 and finish_reason == "length" and has_reasoning:
            retry_tokens = min(max(max_tokens * 2, 4000), 6000)
            logger.warning(
                "LLM response ended during reasoning provider=%s model=%s; retrying with max_tokens=%s",
                provider,
                model,
                retry_tokens,
            )
            continue
        logger.error(
            "LLM returned empty content provider=%s model=%s finish_reason=%s reasoning_only=%s",
            provider,
            model,
            finish_reason,
            has_reasoning,
        )
        detail = "LLM returned an empty response"
        if finish_reason:
            detail += " (finish_reason=" + str(finish_reason) + ")"
        raise LLMEmptyResponseError(detail)

import asyncio
import logging

logger = logging.getLogger(__name__)

RETRYABLE_EXC = (APIConnectionError, APITimeoutError, RateLimitError)


async def call_llm_with_retry(*args, retries: int = 1, **kwargs):
    """Wrap call_llm with one-shot retry on transient errors.

    review.md P1-5: 30s timeout already enforced inside call_llm; we add a
    single retry for connection / 5xx / rate-limit failures. 4xx (incl. 429
    surfaced as RateLimitError) is retried once; 4xx other than 429 (bad
    request) is NOT retried.
    """
    last_err = None
    for attempt in range(retries + 1):
        try:
            return await call_llm(*args, **kwargs)
        except RETRYABLE_EXC as e:
            last_err = e
            if attempt >= retries:
                raise
            logger.warning("LLM transient error (attempt %d): %s -- retrying", attempt + 1, e)
            await asyncio.sleep(0.5 * (attempt + 1))
        except APIError as e:
            status = getattr(e, 'status_code', None)
            if status and 500 <= int(status) < 600 and attempt < retries:
                last_err = e
                logger.warning("LLM server error (attempt %d): %s -- retrying", attempt + 1, e)
                await asyncio.sleep(0.5 * (attempt + 1))
                continue
            raise
    raise last_err
