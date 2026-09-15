# src/models/ToolCall.py

from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class ToolCall:

    name: str
    approved: bool = False
    valid: bool = False
    path: str = field(default_factory=str)
    args: Dict[str, Any] = field(default_factory=dict)
