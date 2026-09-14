from typing import Any, Dict, List, Optional

from src.Utils.logger import get_logger
from src.Context.ContextBuilder import ContextBuilder
from src.Context.ContextWindow import ContextWindow, Message
from src.Context.Compactor import Compactor
from src.Context.TokenBudget import TokenBudget
from src.Engine.LlmProviderManager import LlmProvider
from src.Engine.providers.LLMResult import LLMResult
from src.Agent.AgentState import AgentState


logger = get_logger("[CONTEXTMANAGER]")


class ContextManager:

    def __init__(
        self,
        config: Dict[str, Any],
        LlmProvider: LlmProvider,
    ) -> None:

        self.config = config
        self.llm_provider = LlmProvider

        self.context_builder = ContextBuilder(
            ContextWindow()
        )

        self.compactor = Compactor(
            self.llm_provider
        )

        self.token_budget = TokenBudget(
            self.config,
            self.llm_provider
        )

        context_config = self.config.get("context") or {}


        self.compaction_target_tokens = max(
            512,
            int(
                context_config.get(
                    "compaction_target_tokens",
                    min(
                        4096,
                        int(self.token_budget.budget * 0.05),
                    ),
                )
            ),
        )

        self.recent_messages_to_keep = max(
            2,
            int(
                context_config.get(
                    "recent_messages_to_keep",
                    6,
                )
            ),
        )

        self.compacted_trajectory: Optional[
            List[Message]
        ] = None

        self.compacted_until_step = 0

        self._last_built_context: Optional[
            List[Message]
        ] = None


    def _build_trajectory(
        self,
        events: List[Any],
    ) -> List[Message]:

        return [
            self.context_builder._event_to_message(event)
            for event in events
            if event.event_type.lower() != "user_input"
        ]


    def _message_to_compaction_text(
        self,
        message: Message,
    ) -> str:

        role = str(
            message.get(
                "role",
                "unknown",
            )
        )

        content = str(
            message.get(
                "content",
                "",
            ) or ""
        )

        parts = [
            f"[{role}]"
        ]

        if content:
            parts.append(content)

        tool_name = message.get("tool_name")

        if tool_name:
            parts.append(
                f"tool_name={tool_name}"
            )

        tool_calls = message.get("tool_calls")

        if tool_calls:
            parts.append(
                f"tool_calls={tool_calls}"
            )

        return " ".join(parts)


    def _compact_trajectory(
        self,
        trajectory: List[Message],
        target_tokens: int,
    ) -> List[Message]:

        if not trajectory:
            return []

        context_text = "\n".join(
            self._message_to_compaction_text(message)
            for message in trajectory
        )

        compacted_text = self.compactor.compact(
            context_text,
            target_tokens,
        )

        if not compacted_text or not compacted_text.strip():
            logger.error(
                "Compactor returned an empty result."
            )
            return []

        return [
            {
                "role": "assistant",
                "content": (
                    "[COMPACTED HISTORY]\n"
                    f"{compacted_text.strip()}"
                ),
            }
        ]


    def _build_context(
        self,
        user_input: str,
        agent_state: Optional[AgentState],
        compacted_history: List[Message],
        recent_trajectory: List[Message],
    ) -> List[Message]:

        return self.context_builder.build_context(
            user_input=user_input,
            stm_result=recent_trajectory,
            agent_state=agent_state,
            compacted_history=compacted_history,
        )


    def _estimate_tokens(
        self,
        messages: List[Message],
    ) -> int:

        return self.token_budget.estimate_messages_tokens(
            messages
        )


    def _compact_if_needed(
        self,
        messages: List[Message],
        recent_events: List[Any],
        compacted_history: List[Message],
        recent_trajectory: List[Message],
        current_step: int,
        user_input: str,
        agent_state: Optional[AgentState],
    ) -> List[Message]:

        estimated_tokens = self._estimate_tokens(
            messages
        )


        if estimated_tokens <= self.token_budget.budget:
            return messages

        logger.warning(
            f"Estimated context exceeds budget at step "
            f"{current_step}: "
            f"estimated={estimated_tokens}, "
            f"budget={self.token_budget.budget}"
        )

        keep_count = min(
            self.recent_messages_to_keep,
            len(recent_events),
        )

        if keep_count > 0:

            events_to_compact = (
                recent_events[:-keep_count]
            )

            recent_events_to_keep = (
                recent_events[-keep_count:]
            )

        else:

            events_to_compact = list(
                recent_events
            )

            recent_events_to_keep = []


        trajectory_to_compact = (
            compacted_history
            + self._build_trajectory(
                events_to_compact
            )
        )

        if not trajectory_to_compact:

            logger.warning(
                "Context exceeds budget but there is "
                "no older trajectory available for compaction."
            )

            return messages


        compacted = self._compact_trajectory(
            trajectory_to_compact,
            self.compaction_target_tokens,
        )

        if not compacted:

            logger.warning(
                "Context compaction failed; "
                "keeping existing context."
            )

            return messages


        self.compacted_trajectory = compacted

        if events_to_compact:

            self.compacted_until_step = (
                events_to_compact[-1].step
            )


        recent_to_keep = self._build_trajectory(
            recent_events_to_keep
        )


        rebuilt = self._build_context(
            user_input=user_input,
            agent_state=agent_state,
            compacted_history=compacted,
            recent_trajectory=recent_to_keep,
        )


        final_estimate = self._estimate_tokens(
            rebuilt
        )

        logger.info(
            f"Context compacted at step "
            f"{current_step}: "
            f"estimated={final_estimate}, "
            f"compacted_until_step="
            f"{self.compacted_until_step}, "
            f"raw_tail={len(recent_to_keep)}"
        )

        return rebuilt


    def build_agent_context(
        self,
        previous_response: Optional[LLMResult],
        user_input: str = "",
        stm_result: Optional[List[Any]] = None,
        agent_state: Optional[AgentState] = None,
    ) -> List[Message]:

        if (
            previous_response is not None
            and self._last_built_context is not None
        ):

            self.token_budget.calibrate_from_response(
                self._last_built_context,
                previous_response,
            )


        events = stm_result or []


        non_user_events = [
            event
            for event in events
            if event.event_type.lower() != "user_input"
        ]

        if self.compacted_trajectory is None:

            compacted_history = []

            recent_events = list(
                non_user_events
            )

        else:

            compacted_history = list(
                self.compacted_trajectory
            )

            recent_events = [
                event
                for event in non_user_events
                if event.step > self.compacted_until_step
            ]


        recent_trajectory = self._build_trajectory(
            recent_events
        )


        messages = self._build_context(
            user_input=user_input,
            agent_state=agent_state,
            compacted_history=compacted_history,
            recent_trajectory=recent_trajectory,
        )


        messages = self._compact_if_needed(
            messages=messages,
            recent_events=recent_events,
            compacted_history=compacted_history,
            recent_trajectory=recent_trajectory,
            current_step=(
                events[-1].step
                if events
                else self.compacted_until_step
            ),
            user_input=user_input,
            agent_state=agent_state,
        )


        estimated_tokens = self._estimate_tokens(
            messages
        )

        logger.debug(
            f"Context prepared | "
            f"estimated_tokens={estimated_tokens}, "
            f"budget={self.token_budget.budget}, "
            f"messages={len(messages)}, "
            f"chars_per_token="
            f"{self.token_budget.chars_per_token:.3f}"
        )

        self._last_built_context = messages


        return messages