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

        self.context_builder = ContextBuilder(ContextWindow())

        self.compactor = Compactor(self.llm_provider)

        self.token_budget = TokenBudget(self.config, self.llm_provider)

        context_config = self.config.get("context") or {}

        self.compaction_target_tokens = max(
            512,
            int(
                context_config.get(
                    "compaction_target_tokens",
                    min(4096, int(self.token_budget.budget * 0.05)),
                )
            ),
        )

        # Number of complete trajectory blocks preserved
        # after a real context compaction.
        self.recent_blocks_to_keep = max(
            2,
            int(
                context_config.get(
                    "recent_blocks_to_keep",
                    6,
                )
            ),
        )

        self.compacted_trajectory: Optional[List[Message]] = None

        self.compacted_until_step = 0

        self._last_built_context: Optional[List[Message]] = None

    def set_workspace(
        self,
        root: str,
        state: str = "",
    ):
        self.context_builder.set_workspace(
            root,
            state,
        )

    # ---------------------------------------------------------
    # Tool-call helpers
    # ---------------------------------------------------------

    def _tool_call_info(
        self,
        event: Any,
    ) -> tuple[str, dict]:

        metadata = (
            event.metadata
            if getattr(
                event,
                "metadata",
                None,
            )
            else {}
        )

        tool_call = metadata.get("tool_call")

        if not isinstance(
            tool_call,
            dict,
        ):
            return "", {}

        function = tool_call.get(
            "function",
            {},
        )

        if not isinstance(
            function,
            dict,
        ):
            return "", {}

        name = (
            str(
                function.get(
                    "name",
                    "",
                )
            )
            .strip()
            .lower()
        )

        arguments = function.get(
            "arguments",
            {},
        )

        if not isinstance(
            arguments,
            dict,
        ):
            arguments = {}

        return name, arguments

    def _tool_call_key(
        self,
        event: Any,
    ) -> tuple:

        name, arguments = self._tool_call_info(event)

        if name in {
            "read",
            "readfile",
        }:

            return (
                "read",
                str(
                    arguments.get(
                        "file_path",
                        "",
                    )
                ),
                str(
                    arguments.get(
                        "start_line",
                        "",
                    )
                ),
                str(
                    arguments.get(
                        "end_line",
                        "",
                    )
                ),
            )

        if name in {
            "edit",
            "editfile",
            "create",
            "createfile",
        }:

            return (
                name,
                str(
                    arguments.get(
                        "file_path",
                        "",
                    )
                ),
            )

        if name == "shell":

            return (
                "shell",
                str(
                    arguments.get(
                        "command",
                        "",
                    )
                ),
                str(
                    arguments.get(
                        "cwd",
                        "",
                    )
                ),
            )

        return (
            name,
            tuple(sorted((str(k), str(v)) for k, v in arguments.items())),
        )

    def _is_read_event(
        self,
        event: Any,
    ) -> bool:

        name, _ = self._tool_call_info(event)

        return name in {
            "read",
            "readfile",
        }

    # ---------------------------------------------------------
    # Deterministic trajectory normalization
    # ---------------------------------------------------------

    def _normalize_events(
        self,
        events: List[Any],
    ) -> List[Any]:

        if not events:
            return []

        normalized: list[Any] = []

        latest_read_index: dict[
            tuple,
            int,
        ] = {}

        for event in events:

            event_type = str(event.event_type).lower()

            # -------------------------------------------------
            # Tool call
            # -------------------------------------------------

            if event_type == "tool_call":

                if self._is_read_event(event):

                    key = self._tool_call_key(event)

                    if key in latest_read_index:

                        old_index = latest_read_index[key]

                        remove_indexes = {
                            old_index,
                        }

                        # Remove the old Read's paired
                        # result when it immediately follows.
                        if old_index + 1 < len(normalized):

                            next_event = normalized[old_index + 1]

                            if str(next_event.event_type).lower() == "tool_result":

                                remove_indexes.add(old_index + 1)

                        normalized = [
                            item
                            for index, item in enumerate(normalized)
                            if index not in remove_indexes
                        ]

                        # Rebuild read indexes after deletion.
                        rebuilt_indexes = {}

                        for (
                            read_key,
                            index,
                        ) in latest_read_index.items():

                            if index in remove_indexes:
                                continue

                            shift = sum(
                                1
                                for removed_index in remove_indexes
                                if removed_index < index
                            )

                            rebuilt_indexes[read_key] = index - shift

                        latest_read_index = rebuilt_indexes

                    latest_read_index[key] = len(normalized)

                normalized.append(event)

                continue

            # -------------------------------------------------
            # Tool result
            # -------------------------------------------------

            if event_type == "tool_result":

                metadata = (
                    event.metadata
                    if getattr(
                        event,
                        "metadata",
                        None,
                    )
                    else {}
                )

                tool_name = (
                    str(
                        metadata.get(
                            "tool_name",
                            "",
                        )
                    )
                    .strip()
                    .lower()
                )

                failure_count = metadata.get("failure_count")

                repeated_failure = bool(
                    metadata.get(
                        "repeated_failed_call",
                        False,
                    )
                )

                recovery_required = bool(
                    metadata.get(
                        "recovery_required",
                        False,
                    )
                )

                is_failure = (
                    failure_count is not None or repeated_failure or recovery_required
                )

                if is_failure:

                    # Collapse consecutive failure/recovery
                    # messages for the same tool.
                    if normalized:

                        previous = normalized[-1]

                        if str(previous.event_type).lower() == "tool_result":

                            previous_metadata = (
                                previous.metadata
                                if getattr(
                                    previous,
                                    "metadata",
                                    None,
                                )
                                else {}
                            )

                            previous_tool = (
                                str(
                                    previous_metadata.get(
                                        "tool_name",
                                        "",
                                    )
                                )
                                .strip()
                                .lower()
                            )

                            previous_is_failure = (
                                previous_metadata.get("failure_count") is not None
                                or bool(
                                    previous_metadata.get(
                                        "repeated_failed_call",
                                        False,
                                    )
                                )
                                or bool(
                                    previous_metadata.get(
                                        "recovery_required",
                                        False,
                                    )
                                )
                            )

                            if previous_is_failure and previous_tool == tool_name:

                                normalized[-1] = event
                                continue

                    normalized.append(event)

                    continue

                normalized.append(event)

                continue

            normalized.append(event)

        return normalized

    # ---------------------------------------------------------
    # Event -> model messages
    # ---------------------------------------------------------

    def _build_trajectory(
        self,
        events: List[Any],
    ) -> List[Message]:

        normalized_events = self._normalize_events(events)

        return [
            self.context_builder._event_to_message(event)
            for event in normalized_events
            if str(event.event_type).lower() != "user_input"
        ]

    # ---------------------------------------------------------
    # Safe trajectory blocks
    # ---------------------------------------------------------

    def _build_blocks(
        self,
        events: List[Any],
    ) -> List[List[Any]]:

        normalized = self._normalize_events(events)

        if not normalized:
            return []

        blocks: list[list[Any]] = []

        current: list[Any] = []

        for event in normalized:

            event_type = str(event.event_type).lower()

            if event_type == "tool_call":

                if current:

                    blocks.append(current)

                current = [event]

                continue

            if (
                event_type == "tool_result"
                and current
                and str(current[-1].event_type).lower() == "tool_call"
            ):

                current.append(event)

                blocks.append(current)

                current = []

                continue

            if current:

                blocks.append(current)

            current = [event]

        if current:

            blocks.append(current)

        return blocks

    def _blocks_to_messages(
        self,
        blocks: List[List[Any]],
    ) -> List[Message]:

        messages: list[Message] = []

        for block in blocks:

            for event in block:

                messages.append(self.context_builder._event_to_message(event))

        return messages

    # ---------------------------------------------------------
    # Compaction
    # ---------------------------------------------------------

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
            )
            or ""
        )

        parts = [f"[{role}]"]

        if content:

            parts.append(content)

        tool_calls = message.get("tool_calls")

        if tool_calls:

            parts.append(f"tool_calls={tool_calls}")

        return " ".join(parts)

    def _compact_trajectory(
        self,
        trajectory: List[Message],
        target_tokens: int,
    ) -> List[Message]:

        if not trajectory:

            return []

        context_text = "\n".join(
            self._message_to_compaction_text(message) for message in trajectory
        )

        compacted_text = self.compactor.compact(
            context_text,
            target_tokens,
        )

        if not compacted_text or not compacted_text.strip():

            logger.error("Compactor returned an empty result.")

            return []

        return [
            {
                "role": "assistant",
                "content": ("[COMPACTED HISTORY]\n" + compacted_text.strip()),
            }
        ]

    # ---------------------------------------------------------
    # Build context
    # ---------------------------------------------------------

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

        return self.token_budget.estimate_messages_tokens(messages)

    # ---------------------------------------------------------
    # Compact only when the real budget is exceeded
    # ---------------------------------------------------------

    def _compact_if_needed(
        self,
        messages: List[Message],
        recent_events: List[Any],
        compacted_history: List[Message],
        current_step: int,
        user_input: str,
        agent_state: Optional[AgentState],
    ) -> List[Message]:

        estimated_tokens = self._estimate_tokens(messages)

        # IMPORTANT:
        # Do not remove history merely because it is old.
        # As long as the prompt fits the budget, preserve it.
        if estimated_tokens <= self.token_budget.budget:

            return messages

        logger.warning(
            f"Estimated context exceeds budget at step "
            f"{current_step}: "
            f"estimated={estimated_tokens}, "
            f"budget={self.token_budget.budget}"
        )

        blocks = self._build_blocks(recent_events)

        if len(blocks) <= self.recent_blocks_to_keep:

            logger.warning(
                "Context exceeds budget but there are "
                "not enough complete trajectory blocks "
                "available for compaction."
            )

            return messages

        blocks_to_compact = blocks[: -self.recent_blocks_to_keep]

        blocks_to_keep = blocks[-self.recent_blocks_to_keep :]

        events_to_compact = [event for block in blocks_to_compact for event in block]

        if not events_to_compact:

            return messages

        trajectory_to_compact: list[Message] = []

        if compacted_history:

            trajectory_to_compact.extend(compacted_history)

        trajectory_to_compact.extend(self._blocks_to_messages(blocks_to_compact))

        compacted = self._compact_trajectory(
            trajectory_to_compact,
            self.compaction_target_tokens,
        )

        if not compacted:

            logger.warning("Context compaction failed; " "keeping existing context.")

            return messages

        self.compacted_trajectory = compacted

        self.compacted_until_step = events_to_compact[-1].step

        recent_to_keep = self._blocks_to_messages(blocks_to_keep)

        rebuilt = self._build_context(
            user_input=user_input,
            agent_state=agent_state,
            compacted_history=compacted,
            recent_trajectory=recent_to_keep,
        )

        final_estimate = self._estimate_tokens(rebuilt)

        logger.info(
            f"Context compacted at step "
            f"{current_step}: "
            f"estimated={final_estimate}, "
            f"compacted_until_step="
            f"{self.compacted_until_step}, "
            f"raw_blocks={len(blocks_to_keep)}"
        )

        return rebuilt

    # ---------------------------------------------------------
    # Public context builder
    # ---------------------------------------------------------

    def build_agent_context(
        self,
        previous_response: Optional[LLMResult],
        user_input: str = "",
        stm_result: Optional[List[Any]] = None,
        agent_state: Optional[AgentState] = None,
    ) -> List[Message]:

        if previous_response is not None and self._last_built_context is not None:

            self.token_budget.calibrate_from_response(
                self._last_built_context,
                previous_response,
            )

        events = stm_result or []

        non_user_events = [
            event for event in events if str(event.event_type).lower() != "user_input"
        ]

        normalized_events = self._normalize_events(non_user_events)

        if self.compacted_trajectory is None:

            compacted_history = []

            # Preserve ALL normalized history while it fits.
            recent_events = normalized_events

        else:

            compacted_history = list(self.compacted_trajectory)

            recent_events = [
                event
                for event in normalized_events
                if event.step > self.compacted_until_step
            ]

        # IMPORTANT:
        # Do not trim to recent_blocks_to_keep here.
        # History is trimmed only by _compact_if_needed()
        # after the actual budget is exceeded.
        recent_trajectory = self._build_trajectory(recent_events)

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
            current_step=(events[-1].step if events else self.compacted_until_step),
            user_input=user_input,
            agent_state=agent_state,
        )

        estimated_tokens = self._estimate_tokens(messages)

        logger.debug(
            f"Context prepared | "
            f"estimated_tokens={estimated_tokens}, "
            f"budget={self.token_budget.budget}, "
            f"messages={len(messages)}, "
            f"raw_events={len(non_user_events)}, "
            f"normalized_events={len(normalized_events)}, "
            f"chars_per_token="
            f"{self.token_budget.chars_per_token:.3f}"
        )

        self._last_built_context = messages

        return messages
