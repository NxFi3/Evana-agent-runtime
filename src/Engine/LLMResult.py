#src/Engine/LLMResult.py

from dataclasses import dataclass
from typing import Any , Dict
@dataclass
class LLMResult:
    response: str
    message: Dict
    tool_calls: list
    thinking: str | None
    usage: Dict
    raw: Any = None