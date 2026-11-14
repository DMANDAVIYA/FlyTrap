"""What a role decides in one turn: thoughts to show, tool calls to make, a note to leave."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Intent:
    tool: str
    args: dict
    reason: str
    evidence: list[int] = field(default_factory=list)


@dataclass
class Plan:
    thoughts: list[tuple[str, str]] = field(default_factory=list)   # (session or "-", text)
    intents: list[Intent] = field(default_factory=list)
    notes: list[tuple[str, str, list[int]]] = field(default_factory=list)  # (session or "-", note, evidence)

    def think(self, session: str, text: str) -> None:
        self.thoughts.append((session, text))

    def act(self, tool: str, reason: str, evidence: list[int] | None = None, **args) -> None:
        self.intents.append(Intent(tool, args, reason, evidence or []))

    def note(self, session: str, text: str, evidence: list[int] | None = None) -> None:
        self.notes.append((session, text, evidence or []))

    @property
    def empty(self) -> bool:
        return not (self.thoughts or self.intents or self.notes)
