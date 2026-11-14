"""One small client for every provider, via their OpenAI-compatible chat APIs.

A model setting is an ordered, comma-separated list of "provider:model" ids:

    RAIDER_MODEL_PANDORA=qwen:qwen-plus,openrouter:qwen/qwen-plus,deepseek:deepseek-chat

- ids whose provider has no API key are skipped, so a list can name providers you
  may never get a key for;
- if a call fails, the next id is tried, and a failing provider sits out for a
  minute so a dead API doesn't add a timeout to every call;
- if nothing is available or everything fails, callers fall back to rules mode.

Base URLs can be overridden with <PROVIDER>_BASE_URL (Qwen and Kimi have regional hosts).
"""

from __future__ import annotations

import json
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
    "openrouter": ("https://openrouter.ai/api/v1", ("OPENROUTER_API_KEY",)),
}
COOL_DOWN_S = 60.0


class LLMError(Exception):
    pass


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

    def mark_down(self) -> None:
        Endpoint._down_until[self.spec] = time.monotonic() + COOL_DOWN_S

    async def chat(self, messages: list[dict], tools: list[dict] | None, temperature: float, max_tokens: int,
                   json_mode: bool) -> Reply:
        body: dict = {"model": self.model, "messages": messages}
        if self.provider == "openai":  # newer OpenAI models take max_completion_tokens and only the default temperature
            body["max_completion_tokens"] = max_tokens
        else:
            body.update(temperature=temperature, max_tokens=max_tokens)
        if tools:
            body["tools"] = tools
            body["tool_choice"] = "auto"
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(f"{self.base}/chat/completions", json=body,
                                         headers={"Authorization": f"Bearer {self.key}"})
        except httpx.HTTPError as exc:
            raise LLMError(f"{self.spec} unreachable: {exc}") from exc
        if resp.status_code >= 300:
            raise LLMError(f"{self.spec} HTTP {resp.status_code}: {resp.text[:200]}")
        try:
            msg = resp.json()["choices"][0]["message"]
        except (ValueError, KeyError, IndexError) as exc:
            raise LLMError(f"bad response from {self.spec}") from exc
        return _parse(msg, self.spec)


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

    def __init__(self, spec: str, timeout: float = 20.0) -> None:
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
                   max_tokens: int = 800, json_mode: bool = False) -> Reply:
        candidates = [e for e in self.endpoints if e.ready] or [e for e in self.endpoints if e.configured]
        if not candidates:
            raise LLMError("no model with an API key")
        errors = []
        for endpoint in candidates:
            try:
                return await endpoint.chat(messages, tools, temperature, max_tokens, json_mode)
            except LLMError as exc:
                endpoint.mark_down()
                errors.append(str(exc))
        raise LLMError("all models failed: " + " | ".join(errors))


def tool_schema(name: str, description: str, properties: dict, required: list[str]) -> dict:
    return {"type": "function", "function": {
        "name": name, "description": description,
        "parameters": {"type": "object", "properties": properties, "required": required},
    }}
