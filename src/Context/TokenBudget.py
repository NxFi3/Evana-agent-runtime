#src/Context/TokenBudge.py

from typing import Any, Dict
from src.Utils.logger import get_logger 
from src.Engine.llmManagment.LlmProvider import LlmProvider 
logger = get_logger("[TOKENBUDGET]")

class TokenBudget:
    def __init__(self, config:Dict[str, Any],llm_provider:LlmProvider) -> None:
        self.config = config 
        self.llm_provider = llm_provider
        self.budget = self.config.get("token_budget", -1)
        self.safe_marigin = self.config.get("safe_margin", -1)
        if self.safe_marigin < 0:
            logger.warning("Safe margin is set to -1,using 10% of model's context length as safe margin.")
            self.safe_marigin =  (self.llm_provider.model.get_model_context_length()) * 0.1
        self.token_budget_previous = 0
    def remaining_budget(self,ModelResponse:Dict[str,Any]) -> int:
        try:
            if self.budget < 0:
                logger.warning("Token budget is set to -1, Usinng model's context length as budget.")
                max_tokens = self.llm_provider.model.get_model_context_length()
                used_tokens = ModelResponse.get('prompt_eval_count',0)
                return max_tokens - used_tokens
            else:
                used_tokens = ModelResponse.get('prompt_eval_count',0)
                return self.budget - used_tokens
            
        except Exception as e:
            logger.error(f"Error calculating remaining budget: {e}")
            return 0
        
    def is_within_budget(self,ModelResponse:Dict[str,Any]) -> bool:
        remaining = self.remaining_budget(ModelResponse)
        if remaining < self.safe_marigin:
            logger.warning(f"Token budget exceeded. Remaining tokens: {remaining}. Safe margin: {self.safe_marigin}")
            return False
        return True
