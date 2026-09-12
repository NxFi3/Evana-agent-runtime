#src/Agent/AgentState.py

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AgentState:
    task: str

    iteration: int = 0
    phase: str = "initializing"

    last_action: str | None = None
    last_observation: str | None = None

    history: dict[str, list[Any]] = field(
        default_factory=lambda: {
            "tool_calls": [],
            "failures": [],
        }
    )

    progress: float = 0.0
    completion: bool = False