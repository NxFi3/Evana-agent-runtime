#src/Memory/MemoryEvent.py
from dataclasses import dataclass
from typing import Dict 
from datetime import datetime
@dataclass
class MemoryEvent:
    id:int
    event_type:str
    content:str
    source:str
    step:int
    timestamp:datetime
    metadata:Dict[str, object]