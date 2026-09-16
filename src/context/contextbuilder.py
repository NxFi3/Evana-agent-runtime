from pathlib import Path
from typing import Any

from src.context.compactor import Compactor
from src.context.contextwindow import ContextWindow
from src.context.tokenbudget import TokenBudget
from src.engine.LlmProviderManager import LlmProvider
from src.models.MemoryEvent import MemoryEvent
from src.models.ToolResult import ToolResult


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

            if source == "user" or event_type == "user_input":
                messages.append(
                    {
                        "role": "user",
                        "content": event.content,
                    }
                )

                continue

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

    @staticmethod
    def _tool_result_to_dict(
        result: ToolResult,
    ) -> dict[str, Any]:

        return {
            "success": result.success,
            "name": result.name,
            "content": result.content,
            "metadata": result.metadata,
        }

    def _populate_window(
        self,
        events: list[MemoryEvent],
        tool_result: ToolResult | None,
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

        if tool_result is not None:
            self.window.set_last_observation(self._tool_result_to_dict(tool_result))
        else:
            self.window.set_last_observation({})

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

    def _fit_messages(
        self,
        messages: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:

        if self.tokenbudget.fits(messages):
            return messages

        protected = [message for message in messages if message.get("role") == "system"]

        others = [message for message in messages if message.get("role") != "system"]

        selected: list[dict[str, Any]] = []

        for message in reversed(others):
            candidate = protected + list(reversed(selected)) + [message]

            if self.tokenbudget.fits(candidate):
                selected.append(message)

        selected.reverse()

        result = protected + selected

        # Safety assertion at the builder level.
        # Normally this should always fit.
        if not self.tokenbudget.fits(result):
            return protected

        return result

    def build_context(
        self,
        events: list[MemoryEvent],
        tool_result: ToolResult | None = None,
        task: dict[str, Any] | None = None,
        active_skills: dict[str, Any] | None = None,
        agent_state: dict[str, Any] | None = None,
        progress: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:

        self._populate_window(
            events=events,
            tool_result=tool_result,
            task=task,
            active_skills=active_skills,
            agent_state=agent_state,
            progress=progress,
        )

        messages = self.window.get_prompt()

        if self.tokenbudget.fits(messages):
            return messages

        messages = self._compact_conversation(messages)

        if self.tokenbudget.fits(messages):
            return messages

        return self._fit_messages(messages)
