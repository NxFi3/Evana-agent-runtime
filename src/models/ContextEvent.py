# src/models/ContextEvent.py
from dataclasses import dataclass, field
from enum import StrEnum
from uuid import UUID, uuid4
from datetime import datetime


class ContextRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"
    SYSTEM = "system"


class ContextType(StrEnum):
    MESSAGE = "message"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    EVENT = "event"


class ContextPriority(StrEnum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class ContextEvent:
    role: ContextRole
    type: ContextType
    content: str
    id: UUID = field(default_factory=uuid4)
    priority: ContextPriority = ContextPriority.NORMAL
    step: int = 0
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: dict[str, object] = field(default_factory=dict)
