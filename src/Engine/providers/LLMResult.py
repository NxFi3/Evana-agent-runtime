#src/Engine/llmManagment/LLMResult.py

from dataclasses import dataclass
from typing import Any , Dict
@dataclass
class LLMResult:
    response: str
    message: Dict #raw output
    tool_calls: list
    thinking: str | None
    usage: int
    raw: Any = None