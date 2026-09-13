#src/Agent/AgentState.py

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AgentState:
    task: str
    iteration: int = 0
    phase: str = "initializing"
    last_action: Any = None
    last_observation: Any = None
    workspace_root: str = ""
    workspace_files: list[str] = field(default_factory=list)
    history: dict = field(default_factory=lambda: {
        "tool_calls": [],
        "failures": []
    })
    progress: float = 0.0
    completion: bool = False