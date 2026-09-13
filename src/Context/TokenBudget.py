#src/Context/TokenBudget.py

from typing import Any, Dict
from src.Utils.logger import get_logger
from src.Engine.llmManagment.LlmProvider import LlmProvider

logger = get_logger("[TOKENBUDGET]")


class TokenBudget:
    def __init__(self, config: Dict[str, Any], llm_provider: LlmProvider) -> None:
        
        self.config = config.get("context") or {}
        self.llm_provider = llm_provider

        context_length = self.llm_provider.model.options.get(
            "num_ctx",
            self.llm_provider.model.get_model_context_length()
        )

        self.context_length = int(context_length)

        self.safe_margin = self.config.get("safe_margin", -1)

        if self.safe_margin < 0:
            self.safe_margin = int(self.context_length * 0.15)

        self.budget = self.context_length - self.safe_margin

        logger.info(
            f"Context length={self.context_length}, "
            f"budget={self.budget}, "
            f"safe_margin={self.safe_margin}"
        )

    def used_tokens(self, model_response: Dict[str, Any]) -> int:
        return int(model_response.get("prompt_eval_count", 0))

    def remaining_budget(self, model_response: Dict[str, Any]) -> int:
        return self.budget - self.used_tokens(model_response)

    def is_within_budget(self, model_response: Dict[str, Any]) -> bool:
        remaining = self.remaining_budget(model_response)

        if remaining <= 0:
            logger.warning(
                f"Context budget exceeded: "
                f"used={self.used_tokens(model_response)}, "
                f"budget={self.budget}"
            )
            return False

        return True