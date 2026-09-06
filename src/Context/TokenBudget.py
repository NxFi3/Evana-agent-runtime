#src/Context/TokenBudget.py
from typing import Any, Dict
from src.Utils.logger import get_logger 
from src.Engine.llmManagment.LlmProvider import LlmProvider 

logger = get_logger("[TOKENBUDGET]")


class TokenBudget:
    def __init__(self, config: Dict[str, Any], llm_provider: LlmProvider) -> None:
        self.config = config
        self.llm_provider = llm_provider

        self.budget = self.config.get("token_budget", -1)
        self.safe_margin = self.config.get("safe_margin", -1)

        if self.safe_margin < 0:
            logger.warning(
                "Safe margin is set to -1, using 10% of runtime context length as safe margin."
            )

            context_length = self.llm_provider.model.options.get(
                "num_ctx",
                self.llm_provider.model.get_model_context_length()
            )

            self.safe_margin = int(context_length * 0.1)

        self.token_budget_previous = 0

    def remaining_budget(self, ModelResponse: Dict[str, Any]) -> int:
        try:
            used_tokens = ModelResponse.get("prompt_eval_count", 0)

            if self.budget < 0:
                logger.warning(
                    "Token budget is set to -1, using runtime context length as budget."
                )

                max_tokens = self.llm_provider.model.options.get(
                    "num_ctx",
                    self.llm_provider.model.get_model_context_length()
                )

                return max_tokens - used_tokens

            return self.budget - used_tokens

        except Exception as e:
            logger.error(f"Error calculating remaining budget: {e}")
            return 0

    def is_within_budget(self, ModelResponse: Dict[str, Any]) -> bool:
        remaining = self.remaining_budget(ModelResponse)

        if remaining < self.safe_margin:
            logger.warning(
                f"Token budget exceeded. "
                f"Remaining tokens: {remaining}. "
                f"Safe margin: {self.safe_margin}"
            )
            return False

        return True