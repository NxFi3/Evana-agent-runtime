#src/Context/Compactor.py

from src.Utils.logger import get_logger
from src.Engine.llmManagment.LlmProvider import LlmProvider
from src.Context.CompactorPrompt import BuildCompactorPrompt


class Compactor:
    def __init__(self, llm_provider: LlmProvider):
        self.llm_provider = llm_provider
        self.logger = get_logger(__name__)

    def compact(self, context: str, max_length: int) -> str:

        if len(context) <= max_length:
            return context

        compacted_context = self.llm_provider.generate(BuildCompactorPrompt(context, max_length))
        
        if len(compacted_context) > max_length:
            self.logger.warning("Compacted context exceeds max length. Truncating.")
            return compacted_context[:max_length]

        return compacted_context