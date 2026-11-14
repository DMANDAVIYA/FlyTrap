"""One small client for every provider, via their OpenAI-compatible chat APIs.

Model ids look like "gemini:gemini-flash-latest", "anthropic:claude-haiku-5-5"
or "openrouter:deepseek/deepseek-chat". An empty id means rules mode.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field

import httpx

PROVIDERS = {
    "gemini": ("https://generativelanguage.googleapis.com/v1beta/openai", "GEMINI_API_KEY"),
    "anthropic": ("https://api.anthropic.com/v1", "ANTHROPIC_API_KEY"),
    "openrouter": ("https://openrouter.ai/api/v1", "OPENROUTER_API_KEY"),
}


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


class LLM:
    def __init__(self, spec: str, timeout: float = 20.0) -> None:
        self.spec = spec.strip()
        provider, _, model = self.spec.partition(":")
        self.provider, self.model = provider, model
        base, key_env = PROVIDERS.get(provider, ("", ""))
        self.base, self.key = base, os.getenv(key_env, "") if key_env else ""
        self.timeout = timeout

    @property
    def available(self) -> bool:
        return bool(self.base and self.model and self.key)

    @property
    def label(self) -> str:
        return self.spec if self.available else "rules"

    async def chat(self, messages: list[dict], tools: list[dict] | None = None, temperature: float = 0.2,
                   max_tokens: int = 800, json_mode: bool = False) -> Reply:
        if not self.available:
            raise LLMError("model not configured")
        body: dict = {"model": self.model, "messages": messages, "temperature": temperature, "max_tokens": max_tokens}
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
            raise LLMError(f"{self.provider} unreachable: {exc}") from exc
        if resp.status_code >= 300:
            raise LLMError(f"{self.provider} HTTP {resp.status_code}: {resp.text[:200]}")
        try:
            msg = resp.json()["choices"][0]["message"]
        except (ValueError, KeyError, IndexError) as exc:
            raise LLMError(f"bad response from {self.provider}") from exc
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
        return Reply((msg.get("content") or "").strip(), calls, clean)


def tool_schema(name: str, description: str, properties: dict, required: list[str]) -> dict:
    return {"type": "function", "function": {
        "name": name, "description": description,
        "parameters": {"type": "object", "properties": properties, "required": required},
    }}
