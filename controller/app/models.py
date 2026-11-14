"""Which AI model each agent runs on. Names live here; API keys live in .env.ai.

Each chain is tried left to right. A provider with no key is skipped, a failing model
sits out for a while and the next one answers. If none works, a blue agent runs on
rules and a raider runs its scripted storyline.
"""

from __future__ import annotations

OPUS = "anthropic:claude-opus-5-5"
SONNET = "anthropic:claude-sonnet-5-5"
GEMINI = "gemini:gemini-4-hydrogen"      # best Gemini a free key can call; 4 Argon and 3.1 Pro need billing
DEEPSEEK = "deepseek:deepseek-v4-pro"
DEEPSEEK_FLASH = "deepseek:deepseek-flash"
KIMI = "kimi:kimi-k3.1-pro"
MUSE = "meta:muse-spark-1.3"

CHAINS: dict[str, tuple[str, ...]] = {
    # blue swarm (Argus, Mnemosyne and Hermes are code-only roles)
    "athena": (OPUS, SONNET, GEMINI, DEEPSEEK),        # commander: campaigns, strategy, approvals
    "hephaestus": (OPUS, SONNET, GEMINI, DEEPSEEK),    # builds bait and shapes the trap copies
    "cerberus": (MUSE, OPUS, SONNET, DEEPSEEK),        # holds trapped attackers: pace, blocks, fingerprints
    "clio": (OPUS, SONNET, GEMINI, DEEPSEEK),          # incident report wording
    # red swarm: Chinese models only (test bots that only reach our own lab).
    # Claude and Gemini refuse this job (content_filter), so they never appear here.
    "prometheus": (DEEPSEEK, KIMI, DEEPSEEK_FLASH),    # keys and tokens
    "pandora": (KIMI, DEEPSEEK, DEEPSEEK_FLASH),       # internal files
    "odysseus": (KIMI, DEEPSEEK, DEEPSEEK_FLASH),      # logged-in customer reaching for others' records
    "icarus": (DEEPSEEK, KIMI, DEEPSEEK_FLASH),        # fast mapping of sensitive paths
    "sisyphus": (DEEPSEEK, KIMI, DEEPSEEK_FLASH),      # walks record IDs
}
RED_PROVIDERS = {"deepseek", "kimi", "qwen", "glm"}


def chain(agent: str) -> str:
    """The comma-separated chain LLM() takes; empty (rules mode) for agents without one."""
    return ",".join(CHAINS.get(agent, ()))
