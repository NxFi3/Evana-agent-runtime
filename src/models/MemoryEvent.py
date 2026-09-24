#src/Memory/MemoryEvent.py

from dataclasses import dataclass, field
from typing import Dict
from datetime import datetime
from uuid import UUID, uuid4


@dataclass
class MemoryEvent:
    id: UUID = field(default_factory=uuid4)

    event_type: str = ""
    content: str = ""
    source: str = ""
    step: int = 0
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, object] = field(default_factory=dict)