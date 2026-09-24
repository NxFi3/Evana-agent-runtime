from pathlib import Path

from src.utils.logger import get_logger
from src.models.MemoryEvent import MemoryEvent
from src.agent.agentloop import Loop
from src.engine.LlmProviderManager import LlmProvider


class Agent:
    def __init__(self, config) -> None:
        self.config = config
        self.logger = get_logger("[AGENT]")
        self.workingdirectory = "EvanaEval"
        Path(self.workingdirectory).mkdir(parents=True, exist_ok=True)

        self.llm = LlmProvider(self.config)
        self.loop = Loop(self.config, self.llm)

    def act(self, event: MemoryEvent):
        return self.loop.run(event, self.workingdirectory)

    def set_workingdirectory(self, directory):
        self.workingdirectory = directory
