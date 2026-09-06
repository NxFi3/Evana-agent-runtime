#src/Context/ContextManager.py

from typing import Dict, Any, List, Optional
from src.Utils.logger import get_logger
from src.Context.ContextBuilder import ContextBuilder
from src.Context.Compactor import Compactor
from src.Context.TokenBudget import TokenBudget
logger = get_logger("[CONTEXTMANAGER]")


class ContextManager:

    def __init__(
        self,
        context_builder: ContextBuilder,
        compactor: Compactor,
        token_budget: TokenBudget) -> None:

        self.context_builder = context_builder
        self.compactor = compactor
        self.token_budget = token_budget

        self.compacted_trajectory: Optional[str] = None
        self.compacted_until_step = 0

    def check_context_length(
        self,
        previous_response: Dict[str, Any]) -> bool:

        return self.token_budget.is_within_budget(previous_response)

    def build_agent_context(
        self,
        PreviousResponse: Dict[str, Any],
        User_input: str = "",
        STM_Result: Optional[List[Any]] = None) -> str:

        if STM_Result is None:
            STM_Result = []

        if not STM_Result:

            self.context_builder.build_context(
                User_input,
                []
            )

            return self.context_builder.context_window.prompt()
        current_step = STM_Result[-1].step
        if self.compacted_trajectory is None:
            previous_events = STM_Result[:-1]
            self.context_builder.build_context(User_input,previous_events)

            trajectory = (self.context_builder.context_window.trajectory)
        else:
            new_events = [event for event in STM_Result if (event.step > self.compacted_until_step and event.event_type.lower() != "user_input")]

            trajectory = self.compacted_trajectory
            if new_events:
                trajectory += "\n" + "\n".join(f"Step {event.step}: {event.content}"for event in new_events)
            self.context_builder.build_context(User_input,[])
        self.context_builder.context_window.trajectory = trajectory
        within_budget = self.check_context_length(PreviousResponse)
            

        if not within_budget:

            remaining_tokens = (
                self.token_budget
                .remaining_budget(PreviousResponse)
            )

            logger.warning(f"Context budget exceeded at step {current_step}.Remaining tokens: {remaining_tokens}.Starting compaction.")
            target_tokens = max(1000, remaining_tokens)    
            compacted_trajectory = self.compactor.compact(trajectory,target_tokens)
            self.compacted_trajectory = compacted_trajectory
            self.compacted_until_step = current_step
            self.context_builder.context_window.trajectory = (compacted_trajectory)

            logger.info(f"Context compacted successfully at step "f"{current_step}.")
        return self.context_builder.context_window.prompt()