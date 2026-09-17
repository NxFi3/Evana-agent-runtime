from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolCall:

    name: str

    approved: bool = False
    valid: bool = False

    path: str = ""

    args: dict[str, Any] = field(default_factory=dict)

    # Semantic runtime information.
    action: str = "execute"
    target: str = ""
