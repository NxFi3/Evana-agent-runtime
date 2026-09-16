# src/context/contextbuilder.py

from src.context.contextwindow import ContextWindow
from src.models.MemoryEvent import MemoryEvent
from src.context.compactor import Compactor
from src.context.tokenbudget import TokenBudget
from src.engine.LlmProviderManager import LlmProvider


class contextbuilder:

    def __init__(self, config, llm_provider: LlmProvider):
        self.llm = llm_provider
        self.window = ContextWindow()
        self.compactor = Compactor(self.llm)
        self.tokenbudget = TokenBudget(config,self.llm)

    def build_context(self,Events:list[MemoryEvent]):
        

