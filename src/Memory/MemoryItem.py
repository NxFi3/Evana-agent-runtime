from dataclasses import dataclass
from typing import Optional

import numpy as np


@dataclass
class MemoryItem:
    id: int
    graph: Optional[np.ndarray]
    mem_type: str
    value: str
    embedding: np.ndarray
    created_at: int
    last_access: int
    count: int
    importance: float
    deleted: int