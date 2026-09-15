# src/models/ToolResult.py

from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class ToolResult:
    success: bool
    name: str
    content: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
