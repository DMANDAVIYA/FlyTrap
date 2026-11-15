"""What a role decides in one turn: thoughts to show, tool calls to make, a note to leave."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Intent:
    tool: str
    args: dict
    reason: str
    evidence: list[int] = field(default_factory=list)
    required: bool = False  # a playbook step the AI may add to but never drop


@dataclass
class Plan:
    thoughts: list[tuple[str, str]] = field(default_factory=list)   # (session or "-", text)
    intents: list[Intent] = field(default_factory=list)
    notes: list[tuple[str, str, list[int]]] = field(default_factory=list)  # (session or "-", note, evidence)
    model: str = "rules"  # which "provider:model" made this plan

    def think(self, session: str, text: str) -> None:
        self.thoughts.append((session, text))

    def act(self, tool: str, why: str, cited: list[int] | None = None, /, **args) -> None:
        """Positional-only: `why` and `cited` go to the action log, and every keyword is a tool
        argument, so a tool's own `reason` or `evidence` argument can never clash with them."""
        self.intents.append(Intent(tool, args, why, cited or args.get("evidence") or []))

    def must(self, tool: str, why: str, cited: list[int] | None = None, /, **args) -> None:
        """Like act(), but the step survives when an AI plan replaces the rules plan."""
        self.intents.append(Intent(tool, args, why, cited or args.get("evidence") or [], required=True))

    def note(self, session: str, text: str, evidence: list[int] | None = None) -> None:
        self.notes.append((session, text, evidence or []))

    @property
    def empty(self) -> bool:
        return not (self.thoughts or self.intents or self.notes)


def merge_plans(ai: Plan, rules: Plan) -> Plan:
    """The AI plan wins, but if the model only talked the safe default actions stay, and required
    playbook steps (lockdown, rebuild, key rotation, damage patch) always happen."""
    if not ai.intents:
        ai.intents, ai.notes = rules.intents, rules.notes
        return ai
    chosen = {(i.tool, i.args.get("session")) for i in ai.intents}
    ai.intents += [i for i in rules.intents if i.required and (i.tool, i.args.get("session")) not in chosen]
    return ai
