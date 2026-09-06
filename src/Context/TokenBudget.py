#src/Context/TokenBudge.py

from typing import Any, Dict
from src.Utils.logger import get_logger 
from src.Engine.llmManagment.LlmProvider import LlmProvider 
logger = get_logger("[TOKENBUDGET]")

class TokenBudget:
    def __init__(self, config:Dict[str, Any],llm_provider:LlmProvider) -> None:
        self.config = config 
        self.llm_provider = llm_provider
        self.budget = self.config.get("token_budget", 30000)
        self.safe_marigin = self.config.get("safe_margin", 1000)
        self.token_budget_previous = 0
    def get_model_context_length(self):
        try:
            logger.info("Fetching model context length")

            model_info = self.llm_provider.show_model_info()

            if model_info is None:
                return None

            for key, value in model_info.modelinfo.items():
                if key.endswith(".context_length"):
                    return value

            logger.warning(
                f"Context length not found for model: {self.model_name}"
            )
            return None

        except Exception as e:
            logger.error(f"Error fetching model context length: {e}")
            return None

    def remaining_budget(self,ModelResponse:Dict[str,Any]) -> int:
        used_tokens = ModelResponse.get('prompt_eval_count',0)

        return self.budget - used_tokens
    def is_within_budget(self,ModelResponse:Dict[str,Any]) -> bool:
        remaining = self.remaining_budget(ModelResponse)
        if remaining < self.safe_marigin:
            logger.warning(f"Token budget exceeded. Remaining tokens: {remaining}. Safe margin: {self.safe_marigin}")
            return False
        return True
