#src/Tools/ToolResult.py

from dataclasses import dataclass, field
from typing import Any, Dict

@dataclass
class ToolResult:
    success:bool
    content:str
    metadata:Dict[str,Any] = field(default_factory=dict)

