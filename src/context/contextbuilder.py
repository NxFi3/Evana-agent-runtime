from typing import Any
from pathlib import Path


from src.context.compactor import Compactor
from src.context.tokenbudget import TokenBudget
from src.engine.LlmProviderManager import LlmProvider
from src.models.MemoryEvent import MemoryEvent
from src.context.contextwindow import ContextWindow


def SystemInstructionReader() -> dict[str, str]:
    try:
        path = Path("AgentInstruction/systeminstruction.md")

        with open(path, "r", encoding="utf-8") as f:
            content = f.read().strip()

        if not content:
            return {}

        return {
            "role": "system",
            "content": content,
        }

    except Exception:
        return {}


class ContextBuilder:

    def __init__(
        self,
        config: dict[str, Any],
        llm_provider: LlmProvider,
    ) -> None:
        self.llm = llm_provider

        self.window = ContextWindow()
        self.compactor = Compactor(self.llm)
        self.tokenbudget = TokenBudget(
            config,
            self.llm,
        )

        self.system_instruction = SystemInstructionReader()

    def _build_conversation(
        self,
        events: list[MemoryEvent],
    ) -> list[dict[str, str]]:
        messages: list[dict[str, str]] = []

        for event in events:
            if not event.content:
                continue

            source = getattr(event, "source", "")
            event_type = getattr(event, "event_type", "")

            if source == "user" or event_type == "user_input":
                messages.append(
                    {
                        "role": "user",
                        "content": event.content,
                    }
                )

            elif source in {"assistant", "llm"} and event_type not in {
                "agent_action",
                "tool_call",
            }:
                messages.append(
                    {
                        "role": "assistant",
                        "content": event.content,
                    }
                )

        return messages

    def _build_last_action(
        self,
        events: list[MemoryEvent],
    ) -> dict[str, Any]:
        for event in reversed(events):
            event_type = getattr(
                event,
                "event_type",
                "",
            )

            if event_type in {
                "agent_action",
                "tool_call",
            }:
                return {
                    "event_type": event_type,
                    "source": getattr(event, "source", ""),
                    "content": event.content,
                    "step": getattr(event, "step", 0),
                    "timestamp": str(getattr(event, "timestamp", "")),
                    "metadata": getattr(
                        event,
                        "metadata",
                        {},
                    ),
                }

        return {}

    def _build_last_observation(
        self,
        events: list[MemoryEvent],
    ) -> dict[str, Any]:
        for event in reversed(events):
            event_type = getattr(
                event,
                "event_type",
                "",
            )

            if event_type == "tool_result":
                return {
                    "event_type": event_type,
                    "source": getattr(event, "source", ""),
                    "content": event.content,
                    "step": getattr(event, "step", 0),
                    "timestamp": str(getattr(event, "timestamp", "")),
                    "metadata": getattr(
                        event,
                        "metadata",
                        {},
                    ),
                }

        return {}

    def _populate_window(
        self,
        events: list[MemoryEvent],
        task: dict[str, Any] | None = None,
        active_skills: dict[str, Any] | None = None,
        agent_state: dict[str, Any] | None = None,
        progress: dict[str, Any] | None = None,
    ) -> None:

        self.window.set_system(self.system_instruction)

        self.window.set_task(task or {})

        self.window.set_active_skills(active_skills or {})

        self.window.set_agent_state(agent_state or {})

        self.window.set_progress(progress or {})

        self.window.set_conversation(self._build_conversation(events))

        self.window.set_last_action(self._build_last_action(events))

        self.window.set_last_observation(self._build_last_observation(events))

    def _compact_conversation(
        self,
        messages: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:

        if not messages:
            return messages

        conversation_messages = [
            message
            for message in messages
            if message.get("role")
            in {
                "user",
                "assistant",
            }
        ]

        if not conversation_messages:
            return messages

        conversation_text = "\n".join(
            f"{message['role']}: " f"{message.get('content', '')}"
            for message in conversation_messages
        )

        target_tokens = max(
            256,
            int(self.tokenbudget.budget * 0.4),
        )

        compacted = self.compactor.compact(
            conversation_text,
            target_tokens,
        )

        if not compacted:
            return messages

        compacted_message = {
            "role": "system",
            "content": (
                "<compacted_conversation>\n"
                f"{compacted}\n"
                "</compacted_conversation>"
            ),
        }

        result: list[dict[str, Any]] = []
        inserted = False

        for message in messages:
            if message.get("role") in {
                "user",
                "assistant",
            }:
                if not inserted:
                    result.append(compacted_message)
                    inserted = True

                continue

            result.append(message)

        if not inserted:
            result.append(compacted_message)

        return result

    def build_context(
        self,
        events: list[MemoryEvent],
        task: dict[str, Any] | None = None,
        active_skills: dict[str, Any] | None = None,
        agent_state: dict[str, Any] | None = None,
        progress: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:

        self._populate_window(
            events=events,
            task=task,
            active_skills=active_skills,
            agent_state=agent_state,
            progress=progress,
        )

        messages = self.window.get_prompt()

        estimated_tokens = self.tokenbudget.estimate_messages_tokens(messages)

        if estimated_tokens <= self.tokenbudget.budget:
            return messages

        messages = self._compact_conversation(messages)

        estimated_tokens = self.tokenbudget.estimate_messages_tokens(messages)

        if estimated_tokens <= self.tokenbudget.budget:
            return messages

        protected_messages = [
            message for message in messages if message.get("role") == "system"
        ]

        non_system_messages = [
            message for message in messages if message.get("role") != "system"
        ]

        final_messages = list(protected_messages)

        for message in reversed(non_system_messages):
            candidate = [
                *protected_messages,
                message,
            ]

            if (
                self.tokenbudget.estimate_messages_tokens(candidate)
                <= self.tokenbudget.budget
            ):
                final_messages.insert(
                    len(protected_messages),
                    message,
                )

        return final_messages
