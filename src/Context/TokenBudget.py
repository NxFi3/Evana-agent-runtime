#src/Context/TokenBudge.py

from typing import Any, Dict
from src.Utils.logger import get_logger 
from src.Engine.llmManagment.LlmProvider import LlmProvider 
logger = get_logger("[TOKENBUDGET]")
class TokenBudge:
    def __init__(self,max_size:int,llmprovider:LlmProvider) -> None:
        self.ContextValue = 0
        self.max_size = max_size
        self.llmprovider = llmprovider
        self.provider = llmprovider.provider_type
    def compute_token_budget(self,ModelResponse:Dict[Any,object]) -> int:
        if self.provider == "ollama":
            self.ContextValue = ModelResponse.get('prompt_eval_count',0)
        return self.ContextValue
    def Compute_Remaining_budget(self,ModelResponse:Dict[Any,object]) -> int:
        if self.provider == "ollama":
            self.ContextValue = ModelResponse.get('prompt_eval_count',0)
            remaining_budget = self.max_size - self.ContextValue
        return remaining_budget

    def is_budget_exceeded(self,ModelResponse:Dict[Any,object]) -> bool:
        self.compute_token_budget(ModelResponse)
        return self.ContextValue > self.max_size

    