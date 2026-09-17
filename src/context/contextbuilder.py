from __future__ import annotations

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

    except (
        FileNotFoundError,
        OSError,
    ):

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
        exclude_event_id: Any = None,
    ) -> list[dict[str, Any]]:

        messages: list[dict[str, Any]] = []

        for event in events:

            event_id = getattr(
                event,
                "id",
                None,
            )

            if exclude_event_id is not None and event_id == exclude_event_id:
                continue

            source = getattr(
                event,
                "source",
                "",
            )

            if source != "user":
                continue

            content = getattr(
                event,
                "content",
                None,
            )

            if content is None:
                continue

            if not isinstance(
                content,
                str,
            ):

                content = str(content)

            content = content.strip()

            if not content:
                continue

            messages.append(
                {
                    "role": "user",
                    "content": content,
                }
            )

        return messages

    def _populate_window(
        self,
        events: list[MemoryEvent],
        task: dict[str, Any] | None,
        agent_state: dict[str, Any] | None,
        progress: dict[str, Any] | None,
        workspace: str | None,
    ) -> None:

        self.window.set_system(self.system_instruction)

        self.window.set_task(task or {})

        self.window.set_agent_state(agent_state or {})

        self.window.set_progress(progress or {})

        self.window.set_runtime(workspace)

        task_event_id = None

        if isinstance(
            task,
            dict,
        ):
            task_event_id = task.get("id")

        self.window.set_conversation(
            self._build_conversation(
                events=events,
                exclude_event_id=task_event_id,
            )
        )

    def _compact_conversation(
        self,
        messages: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:

        conversation = [
            message for message in messages if message.get("role") == "user"
        ]

        if not conversation:
            return messages

        conversation_text = "\n".join(
            f"user: {message.get('content', '')}" for message in conversation
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

        if not system_messages:
            return messages

        system_content = "\n\n".join(
            str(
                message.get(
                    "content",
                    "",
                )
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

    def _fit_messages(
        self,
        messages: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:

        if self.tokenbudget.fits(messages):
            return messages

        system_messages = [
            message for message in messages if message.get("role") == "system"
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

        other_messages = [
            message for message in messages if message.get("role") != "system"
        ]

        selected: list[dict[str, Any]] = []

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

        if self.window.agent_state:
            sections.append(
                ContextWindow._section(
                    "agent_state",
                    self.window.agent_state,
                )
            )

        if self.window.progress:
            sections.append(
                ContextWindow._section(
                    "progress",
                    self.window.progress,
                )
            )

        sections.append(
            ContextWindow._section(
                "runtime",
                self.window.runtime,
            )
        )

        return "\n\n".join(sections)

    def build_context(
        self,
        events: list[MemoryEvent],
        task: dict[str, Any] | None = None,
        agent_state: dict[str, Any] | None = None,
        progress: dict[str, Any] | None = None,
        workspace: str | None = None,
    ) -> list[dict[str, Any]]:

        self._populate_window(
            events=events,
            task=task,
            agent_state=agent_state,
            progress=progress,
            workspace=workspace,
        )

        messages = self.window.get_prompt()

        # 1. Normal context
        if self.tokenbudget.fits(messages):
            return messages

        # 2. Compact only the user conversation
        messages = self._compact_conversation(messages)

        if self.tokenbudget.fits(messages):
            return messages

        # 3. Drop oldest conversation messages
        messages = self._fit_messages(messages)

        if self.tokenbudget.fits(messages):
            return messages

        # 4. Absolute fallback
        return [
            {
                "role": "system",
                "content": (self._minimal_system_context()),
            }
        ]
