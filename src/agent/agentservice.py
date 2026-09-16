from src.utils.logger import get_logger
from src.models.MemoryEvent import MemoryEvent
from src.agent.agentloop import *


class Agent:
    def __init__(self) -> None:

        self.logger = get_logger("[AGENT]")

    def act(self, event: MemoryEvent): ...
