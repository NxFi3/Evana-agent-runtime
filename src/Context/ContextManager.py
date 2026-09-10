from typing import Dict, Any, List, Optional
from src.Utils.logger import get_logger
from src.Context.ContextBuilder import ContextBuilder
from src.Context.ContextWindow import ContextWindow, Message
from src.Context.Compactor import Compactor
from src.Context.TokenBudget import TokenBudget
from src.Engine.llmManagment.LlmProvider import LlmProvider

logger = get_logger("[CONTEXTMANAGER]")


class ContextManager:
    def __init__(self, config: Dict[str, Any], LlmProvider: LlmProvider) -> None:
        self.config = config
        self.llm_provider = LlmProvider
        self.context_builder = ContextBuilder(ContextWindow())
        self.compactor = Compactor(self.llm_provider)
        self.token_budget = TokenBudget(self.config, self.llm_provider)
        self.compacted_trajectory: Optional[List[Message]] = None
        self.compacted_until_step = 0

    def check_context_length(self, previous_response: Dict[str, Any]) -> bool:
        return self.token_budget.is_within_budget(previous_response)

    def _build_trajectory(self, events: List[Any]) -> List[Message]:
        return [self.context_builder._event_to_message(event) for event in events]

    def _compact_trajectory(self, trajectory: List[Message], target_tokens: int) -> List[Message]:
        text = "\n".join(
            f"[{message.get('role', 'unknown')}] {message.get('content', '')}"
            for message in trajectory
        )
        compacted_text = self.compactor.compact(text, target_tokens)
        return [{"role": "assistant", "content": compacted_text}]

    def build_agent_context(
        self,
        PreviousResponse: Dict[str, Any],
        User_input: str = "",
        STM_Result: Optional[List[Any]] = None
    ) -> List[Message]:
        STM_Result = STM_Result or []
        current_step = STM_Result[-1].step if STM_Result else self.compacted_until_step

        if self.compacted_trajectory is None:
            self.context_builder.build_context(User_input, STM_Result)
        else:
            new_events = [
                event for event in STM_Result
                if event.step > self.compacted_until_step and event.event_type.lower() != "user_input"
            ]
            trajectory = list(self.compacted_trajectory)
            trajectory.extend(self._build_trajectory(new_events))
            self.context_builder.build_context(User_input, [])
            self.context_builder.context_window.set_trajectory(trajectory)

        messages = self.context_builder.context_window.prompt()
        within_budget = self.check_context_length(PreviousResponse)

        if not within_budget:
            remaining_tokens = self.token_budget.remaining_budget(PreviousResponse)
            logger.warning(
                f"Context budget exceeded at step {current_step}. "
                f"Remaining tokens: {remaining_tokens}. Starting compaction."
            )
            target_tokens = max(1000, remaining_tokens)
            trajectory = self.context_builder.context_window.trajectory
            self.compacted_trajectory = self._compact_trajectory(trajectory, target_tokens)
            self.compacted_until_step = current_step
            self.context_builder.context_window.set_trajectory(self.compacted_trajectory)
            logger.info(f"Context compacted successfully at step {current_step}.")

        return self.context_builder.context_window.prompt()
