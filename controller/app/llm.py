"""One small client for every provider, via their OpenAI-compatible chat APIs.

A model chain (see models.py) is an ordered, comma-separated list of "provider:model" ids:

    "kimi:kimi-k3.1-pro,meta:muse-spark-1.3,deepseek:deepseek-v4-pro"

- ids whose provider has no API key are skipped, so a list can name providers you
  may never get a key for;
- a rate limit or server error is retried on the same model first;
- if a call still fails, the next id answers that call. A failing backup sits out
  for a minute; the first model never sits out (it is tried first on every call)
  unless its key is bad or out of credits;
- if nothing is available or everything fails, callers fall back to rules mode.

Base URLs can be overridden with <PROVIDER>_BASE_URL (Qwen and Kimi have regional hosts).
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass, field

import httpx

# provider -> (default base URL, API key env vars; the first one that is set wins)
PROVIDERS = {
    "gemini": ("https://generativelanguage.googleapis.com/v1beta/openai", ("GEMINI_API_KEY",)),
    "anthropic": ("https://api.anthropic.com/v1", ("ANTHROPIC_API_KEY",)),
    "openai": ("https://api.openai.com/v1", ("OPENAI_API_KEY",)),
    "deepseek": ("https://api.deepseek.com", ("DEEPSEEK_API_KEY",)),
    "qwen": ("https://dashscope-intl.aliyuncs.com/compatible-mode/v1", ("QWEN_API_KEY", "DASHSCOPE_API_KEY")),
    "kimi": ("https://api.moonshot.ai/v1", ("KIMI_API_KEY", "MOONSHOT_API_KEY")),
    "glm": ("https://api.z.ai/api/paas/v4", ("GLM_API_KEY", "ZHIPU_API_KEY")),
    "meta": ("https://api.meta.ai/v1", ("MUSE_API_KEY", "META_API_KEY")),
    "openrouter": ("https://openrouter.ai/api/v1", ("OPENROUTER_API_KEY",)),
}
COOL_DOWN_S = 60.0
LONG_COOL_DOWN_S = 900.0                 # bad key or no credits: won't fix itself in a minute
LONG_STATUSES = {"401", "402", "403"}
RETRY_STATUSES = {429, 500, 502, 503, 504, 529}  # transient: try the same model again
RETRIES = 2
MAX_RETRY_WAIT_S = 8.0
log = logging.getLogger("controller.llm")
NO_TEMPERATURE = {"openai", "anthropic", "kimi"}  # these reject a custom temperature (Kimi K3.x allows only 1)
NO_JSON_MODE = {"anthropic"}             # Anthropic's compat API rejects response_format; the prompt asks for JSON


class LLMError(Exception):
    def __init__(self, message: str, status: int = 0, retry_after: float = 0.0) -> None:
        super().__init__(message)
        self.status = status
        self.retry_after = retry_after


@dataclass
class ToolCall:
    id: str
    name: str
    args: dict


@dataclass
class Reply:
    text: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    message: dict = field(default_factory=dict)  # assistant message to append to history
    model: str = ""                               # which "provider:model" answered


class Endpoint:
    """One provider:model pair."""

    _down_until: dict[str, float] = {}  # shared across instances: a provider that just failed sits out

    def __init__(self, spec: str, timeout: float) -> None:
        self.spec = spec.strip()
        self.provider, _, self.model = self.spec.partition(":")
        default_base, key_envs = PROVIDERS.get(self.provider, ("", ()))
        self.base = os.getenv(f"{self.provider.upper()}_BASE_URL", default_base).rstrip("/")
        self.key = next((os.environ[k] for k in key_envs if os.getenv(k)), "")
        self.timeout = timeout

    @property
    def configured(self) -> bool:
        return bool(self.base and self.model and self.key)

    @property
    def ready(self) -> bool:
        return self.configured and time.monotonic() >= self._down_until.get(self.spec, 0.0)

    def mark_down(self, seconds: float = COOL_DOWN_S) -> None:
        Endpoint._down_until[self.spec] = time.monotonic() + seconds

    async def chat(self, messages: list[dict], tools: list[dict] | None, temperature: float, max_tokens: int,
                   json_mode: bool) -> Reply:
        body: dict = {"model": self.model, "messages": messages}
        # Newer OpenAI models take max_completion_tokens; newer OpenAI, Claude and Kimi models reject a custom temperature.
        body["max_completion_tokens" if self.provider == "openai" else "max_tokens"] = max_tokens
        if self.provider not in NO_TEMPERATURE:
            body["temperature"] = temperature
        if tools:
            body["tools"] = tools
            body["tool_choice"] = "auto"
        if json_mode and self.provider not in NO_JSON_MODE:
            body["response_format"] = {"type": "json_object"}
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(f"{self.base}/chat/completions", json=body,
                                         headers={"Authorization": f"Bearer {self.key}"})
        except httpx.HTTPError as exc:
            raise LLMError(f"{self.spec} unreachable: {exc}") from exc
        if resp.status_code >= 300:
            raise LLMError(f"{self.spec} HTTP {resp.status_code}: {resp.text[:200]}", resp.status_code,
                           _retry_after(resp.headers.get("retry-after")))
        try:
            msg = resp.json()["choices"][0]["message"]
        except (ValueError, KeyError, IndexError) as exc:
            raise LLMError(f"bad response from {self.spec}") from exc
        return _parse(msg, self.spec)


def _retry_after(value: str | None) -> float:
    try:
        return max(0.0, float(value or 0))
    except ValueError:
        return 0.0


def _parse(msg: dict, spec: str) -> Reply:
    calls = []
    for raw in msg.get("tool_calls") or []:
        fn = raw.get("function", {})
        try:
            args = json.loads(fn.get("arguments") or "{}")
        except ValueError:
            args = {}
        calls.append(ToolCall(raw.get("id", ""), fn.get("name", ""), args if isinstance(args, dict) else {}))
    clean = {"role": "assistant", "content": msg.get("content") or ""}
    if msg.get("tool_calls"):
        clean["tool_calls"] = msg["tool_calls"]
    return Reply((msg.get("content") or "").strip(), calls, clean, spec)


class LLM:
    """An ordered fallback chain of endpoints. Empty or keyless means rules mode."""

    def __init__(self, spec: str, timeout: float = 60.0) -> None:  # frontier models can think for a while
        self.endpoints = [Endpoint(s, timeout) for s in (spec or "").split(",") if s.strip()]

    @property
    def available(self) -> bool:
        return any(e.configured for e in self.endpoints)

    @property
    def label(self) -> str:
        """The model a call will try first, or 'rules' if none has a key."""
        ready = [e for e in self.endpoints if e.ready] or [e for e in self.endpoints if e.configured]
        return ready[0].spec if ready else "rules"

    async def chat(self, messages: list[dict], tools: list[dict] | None = None, temperature: float = 0.2,
                   max_tokens: int = 1500, json_mode: bool = False) -> Reply:  # headroom for reasoning models
        configured = [e for e in self.endpoints if e.configured]
        candidates = [e for e in configured if e.ready] or configured
        if not candidates:
            raise LLMError("no model with an API key")
        errors = []
        for endpoint in candidates:
            try:
                return await self._call(endpoint, messages, tools, temperature, max_tokens, json_mode)
            except LLMError as exc:
                errors.append(str(exc))
                bad_key = str(exc.status) in LONG_STATUSES
                if endpoint is configured[0] and not bad_key:
                    log.warning("model %s failed this call, backup answers: %s", endpoint.spec, str(exc)[:160])
                    continue
                wait = LONG_COOL_DOWN_S if bad_key else COOL_DOWN_S
                endpoint.mark_down(wait)
                log.warning("model %s skipped for %.0fs: %s", endpoint.spec, wait, str(exc)[:160])
        raise LLMError("all models failed: " + " | ".join(errors))

    @staticmethod
    async def _call(endpoint: Endpoint, messages: list[dict], tools: list[dict] | None, temperature: float,
                    max_tokens: int, json_mode: bool) -> Reply:
        """One model, with a short retry on rate limits and server errors."""
        for attempt in range(RETRIES + 1):
            try:
                return await endpoint.chat(messages, tools, temperature, max_tokens, json_mode)
            except LLMError as exc:
                if exc.status not in RETRY_STATUSES or attempt == RETRIES:
                    raise
                await asyncio.sleep(min(exc.retry_after or 2.0 * (attempt + 1), MAX_RETRY_WAIT_S))
        raise LLMError(f"{endpoint.spec}: retries exhausted")


def tool_schema(name: str, description: str, properties: dict, required: list[str]) -> dict:
    return {"type": "function", "function": {
        "name": name, "description": description,
        "parameters": {"type": "object", "properties": properties, "required": required},
    }}
