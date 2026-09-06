#src/Context/Compactor.py

from src.Utils.logger import get_logger
from src.Engine.llmManagment.LlmProvider import LlmProvider
from src.Context.CompactorPrompt import BuildCompactorPrompt



class Compactor:
    def __init__(self, llm_provider: LlmProvider):
        self.llm_provider = llm_provider
        self.logger = get_logger(__name__)

    def compact(self, context: str,max_length) -> str:
        try:
            compacted_context = self.llm_provider.generate(BuildCompactorPrompt(context, max_length)).get('response', '')
        except Exception as e:
            self.logger.error(f'unexpected Error : {e}')
            return context
        return compacted_context