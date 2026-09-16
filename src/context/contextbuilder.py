from pathlib import Path
from typing import Any

from src.context.compactor import Compactor
from src.context.contextwindow import ContextWindow
from src.context.tokenbudget import TokenBudget
from src.engine.LlmProviderManager import LlmProvider
from src.models.MemoryEvent import MemoryEvent


def SystemInstructionReader() -> str:
    path = Path("AgentInstruction/systeminstruction.md")

    try:
        return path.read_text(encoding="utf-8").strip()

    except FileNotFoundError:
        return ""

    except OSError:
        return ""


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

            source = getattr(
                event,
                "source",
                "",
            )

            event_type = getattr(
                event,
                "event_type",
                "",
            )

            # User messages
            if source == "user" or event_type == "user_input":

                messages.append(
                    {
                        "role": "user",
                        "content": event.content,
                    }
                )

                continue

            # Assistant messages
            # Tool/agent events are represented separately.
            if source in {
                "assistant",
                "llm",
            } and event_type not in {
                "agent_action",
                "tool_call",
                "tool_result",
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

            if event_type not in {
                "agent_action",
                "tool_call",
            }:
                continue

            return {
                "event_type": event_type,
                "source": getattr(
                    event,
                    "source",
                    "",
                ),
                "content": event.content,
                "step": getattr(
                    event,
                    "step",
                    0,
                ),
                "timestamp": str(
                    getattr(
                        event,
                        "timestamp",
                        "",
                    )
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

            if event_type != "tool_result":
                continue

            return {
                "event_type": event_type,
                "source": getattr(
                    event,
                    "source",
                    "",
                ),
                "content": event.content,
                "step": getattr(
                    event,
                    "step",
                    0,
                ),
                "timestamp": str(
                    getattr(
                        event,
                        "timestamp",
                        "",
                    )
                ),
            }

        return {}

    def _populate_window(
        self,
        events: list[MemoryEvent],
        task: dict[str, Any] | None,
        active_skills: dict[str, Any] | None,
        agent_state: dict[str, Any] | None,
        progress: dict[str, Any] | None,
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

        conversation = [
            message
            for message in messages
            if message.get("role")
            in {
                "user",
                "assistant",
            }
        ]

        if not conversation:
            return messages

        conversation_text = "\n".join(
            f"{message['role']}: " f"{message.get('content', '')}"
            for message in conversation
        )

        compacted = self.compactor.compact(
            conversation_text,
            self.tokenbudget.compaction_target_tokens,
        )

        if not compacted:
            return messages

        system_messages = [
            message for message in messages if message.get("role") == "system"
        ]

        system_content = "\n\n".join(
            message.get(
                "content",
                "",
            )
            for message in system_messages
        )

        merged_system = {
            "role": "system",
            "content": (
                f"{system_content}\n\n"
                "<compacted_conversation>\n"
                f"{compacted}\n"
                "</compacted_conversation>"
            ).strip(),
        }

        return [merged_system]

    def _compact_observation(
        self,
        messages: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:

        system_messages = [
            message for message in messages if message.get("role") == "system"
        ]

        if not system_messages:
            return messages

        system_message = system_messages[0]

        system_content = str(
            system_message.get(
                "content",
                "",
            )
        )

        observation = self.window.last_observation

        if not observation:
            return messages

        observation_text = ContextWindow._serialize(observation)

        compacted = self.compactor.compact(
            observation_text,
            self.tokenbudget.compaction_target_tokens,
        )

        if not compacted:
            return messages

        original_section = ContextWindow._section(
            "last_observation",
            observation,
        )

        compacted_section = (
            "<last_observation>\n" f"{compacted}\n" "</last_observation>"
        )

        if original_section not in system_content:
            return messages

        new_content = system_content.replace(
            original_section,
            compacted_section,
            1,
        )

        return [
            {
                "role": "system",
                "content": new_content,
            },
            *[message for message in messages[1:] if message.get("role") != "system"],
        ]

    def _fit_messages(
        self,
        messages: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:

        if self.tokenbudget.fits(messages):
            return messages

        system_messages = [
            message for message in messages if message.get("role") == "system"
        ]

        other_messages = [
            message for message in messages if message.get("role") != "system"
        ]

        if not system_messages:
            return []

        system_message = system_messages[0]

        if not self.tokenbudget.fits([system_message]):

            return [
                {
                    "role": "system",
                    "content": self._minimal_system_context(),
                }
            ]

        selected: list[dict[str, Any]] = []

        # Keep the newest messages first.
        for message in reversed(other_messages):

            candidate = [
                system_message,
                *reversed(selected),
                message,
            ]

            if self.tokenbudget.fits(candidate):
                selected.append(message)

        selected.reverse()

        result = [
            system_message,
            *selected,
        ]

        if self.tokenbudget.fits(result):
            return result

        return [system_message]

    def _minimal_system_context(
        self,
    ) -> str:

        sections: list[str] = []

        if self.system_instruction:

            sections.append(self.system_instruction)

        if self.window.task:

            sections.append(
                ContextWindow._section(
                    "task",
                    self.window.task,
                )
            )

        if self.window.progress:

            sections.append(
                ContextWindow._section(
                    "progress",
                    self.window.progress,
                )
            )

        if self.window.last_action:

            sections.append(
                ContextWindow._section(
                    "last_action",
                    self.window.last_action,
                )
            )

        sections.append(
            ContextWindow._section(
                "runtime",
                {
                    "os": self.window.os_name,
                },
            )
        )

        return "\n\n".join(sections)

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

        # 1. Normal context
        if self.tokenbudget.fits(messages):
            return messages

        # 2. Compact conversation
        messages = self._compact_conversation(messages)

        if self.tokenbudget.fits(messages):
            return messages

        # 3. Compact tool observation
        messages = self._compact_observation(messages)

        if self.tokenbudget.fits(messages):
            return messages

        # 4. Drop old messages until context fits
        messages = self._fit_messages(messages)

        if self.tokenbudget.fits(messages):
            return messages

        # 5. Absolute fallback
        return [
            {
                "role": "system",
                "content": self._minimal_system_context(),
            }
        ]
