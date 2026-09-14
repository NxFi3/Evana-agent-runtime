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
        context_config = self.config.get("context") or {}
        self.compaction_target_tokens = int(
            context_config.get(
                "compaction_target_tokens",
                min(16384, max(4096, int(self.token_budget.budget * 0.20)))
            )
        )
        self.compacted_trajectory: Optional[List[Message]] = None
        self.compacted_until_step = 0

    def check_context_length(self, previous_response: Dict[str, Any]) -> bool:
        return self.token_budget.is_within_budget(previous_response)

    def _build_trajectory(self, events: List[Any]) -> List[Message]:
        return [
            self.context_builder._event_to_message(event)
            for event in events
        ]

    def _message_to_compaction_text(self, message: Message) -> str:
        role = message.get("role", "unknown")
        content = message.get("content", "")
        parts = [f"[{role}] {content}" if content else f"[{role}]"]

        tool_name = message.get("tool_name")
        if tool_name:
            parts.append(f"tool_name={tool_name}")

        tool_calls = message.get("tool_calls")
        if tool_calls:
            parts.append(f"tool_calls={tool_calls}")

        return " ".join(parts)

    def _compact_trajectory(
        self,
        trajectory: List[Message],
        target_tokens: int
    ) -> List[Message]:
        text = "\n".join(
            self._message_to_compaction_text(message)
            for message in trajectory
        )

        compacted_text = self.compactor.compact(
            text,
            target_tokens
        )

        if not compacted_text.strip():
            logger.error("Context compactor returned an empty result; keeping existing trajectory.")
            return trajectory

        return [{
            "role": "assistant",
            "content": "[COMPACTED AGENT STATE]\n" + compacted_text
        }]

    def set_workspace(self, root: str, state: str = ""):
        self.context_builder.set_workspace(root, state)

    def build_agent_context(
        self,
        PreviousResponse: Dict[str, Any],
        User_input: str = "",
        STM_Result: Optional[List[Any]] = None
    ) -> List[Message]:
        events = STM_Result or []

        current_step = (
            events[-1].step
            if events
            else self.compacted_until_step
        )

        if self.compacted_trajectory is None:
            self.context_builder.build_context(
                User_input,
                events
            )
        else:
            new_events = [
                event
                for event in events
                if (
                    event.step > self.compacted_until_step
                    and event.event_type.lower() != "user_input"
                )
            ]

            trajectory = list(self.compacted_trajectory)
            trajectory.extend(
                self._build_trajectory(new_events)
            )

            self.context_builder.build_context(
                User_input,
                []
            )
            self.context_builder.context_window.set_trajectory(trajectory)

        if not self.check_context_length(PreviousResponse):
            used_tokens = self.token_budget.used_tokens(PreviousResponse)
            logger.warning(
                f"Context budget exceeded at step {current_step}. "
                f"Used tokens: {used_tokens}. "
                f"Budget: {self.token_budget.budget}. "
                f"Starting compaction to ~{self.compaction_target_tokens} tokens."
            )

            trajectory = self.context_builder.context_window.trajectory
            compacted = self._compact_trajectory(
                trajectory,
                self.compaction_target_tokens
            )

            if compacted != trajectory:
                self.compacted_trajectory = compacted
                self.compacted_until_step = current_step
                self.context_builder.context_window.set_trajectory(compacted)
                logger.info(
                    f"Context compacted successfully at step {current_step}."
                )
            else:
                logger.warning("Context compaction was not applied.")

        return self.context_builder.context_window.prompt()
