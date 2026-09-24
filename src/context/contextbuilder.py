from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.context.contextwindow import ContextWindow
from src.context.tokenbudget import TokenBudget
from src.engine.LlmProviderManager import LlmProvider
from src.models.MemoryEvent import MemoryEvent

DEFAULT_INSTRUCTION = (
    "You are Evana, an autonomous assistant and software engineering agent."
)


def SystemInstructionReader() -> str:

    path = Path("AgentInstruction/systeminstruction.md")

    try:
        text = path.read_text(encoding="utf-8").strip()

    except (
        FileNotFoundError,
        OSError,
    ):
        return DEFAULT_INSTRUCTION

    return text or DEFAULT_INSTRUCTION


class ContextBuilder:
    """
    Builds the complete model-visible context.

    Context contains:

        system
            - static agent instruction
            - runtime information

        execution context
            - current task
            - agent state
            - progress
            - working set
            - observations
            - recent actions

        conversation
            - user messages
            - assistant messages
            - native assistant tool_calls
            - native tool results
              with tool_call_id when available

    The execution context is derived from the current runtime state and is
    intentionally kept separate from the persisted conversation events.

    The conversation itself is replayed using the native tool-calling
    protocol so providers such as Ollama/OpenRouter can continue a
    multi-step tool interaction.
    """

    MAX_TOOL_CHARS = 8000
    OLD_TOOL_CHARS = 300
    FULL_TOOL_RESULTS = 6

    MAX_THINKING_CHARS = 2000

    MAX_EXECUTION_CONTEXT_CHARS = 12000

    _TEXT_FIELDS = (
        "content",
        "stdout",
        "stderr",
    )

    def __init__(
        self,
        config: dict[str, Any],
        llm_provider: LlmProvider,
    ) -> None:

        self.config = config

        self.llm = llm_provider

        self.window = ContextWindow()

        self.tokenbudget = TokenBudget(
            config,
            self.llm,
        )

        self.system_instruction = SystemInstructionReader()

    @staticmethod
    def _safe_json(
        value: Any,
    ) -> str:

        try:
            return json.dumps(
                value,
                ensure_ascii=False,
                indent=2,
                default=str,
            )
        except Exception:
            return str(value)

    @staticmethod
    def _last_index(
        messages: list[dict[str, Any]],
        role: str,
    ) -> int:

        for index in range(
            len(messages) - 1,
            -1,
            -1,
        ):

            if messages[index].get("role") == role:
                return index

        return -1

    @staticmethod
    def _truncate(
        value: str,
        limit: int,
    ) -> str:

        value = str(value or "")

        if len(value) <= limit:
            return value

        if limit <= 64:
            return value[:limit]

        omitted = len(value) - limit

        return (
            value[: limit - 64].rstrip()
            + "\n\n"
            + f"... {omitted} characters omitted ..."
        )

    def _build_execution_context(
        self,
        task: dict[str, Any] | None,
        agent_state: dict[str, Any] | None,
        progress: dict[str, Any] | None,
        working_set: dict[str, Any] | None,
        observation: dict[str, Any] | None,
        recent_actions: dict[str, Any] | None,
    ) -> str:
        """
        Build compact, model-facing execution state.

        This state is generated fresh for every iteration and therefore
        reflects the current runtime rather than only persisted history.
        """

        sections: list[str] = []

        if isinstance(task, dict):

            task_content = str(task.get("content") or "").strip()

            if task_content:

                sections.append(
                    "<current_task>\n" f"{task_content}\n" "</current_task>"
                )

        if agent_state:

            sections.append(
                "<agent_state>\n" f"{self._safe_json(agent_state)}\n" "</agent_state>"
            )

        if progress:

            sections.append(
                "<progress>\n" f"{self._safe_json(progress)}\n" "</progress>"
            )

        if working_set:

            sections.append(
                "<working_set>\n" f"{self._safe_json(working_set)}\n" "</working_set>"
            )

        if observation:

            sections.append(
                "<observations>\n" f"{self._safe_json(observation)}\n" "</observations>"
            )

        if recent_actions:

            sections.append(
                "<recent_actions>\n"
                f"{self._safe_json(recent_actions)}\n"
                "</recent_actions>"
            )

        if not sections:
            return ""

        result = "\n\n".join(sections)

        return self._truncate(
            result,
            self.MAX_EXECUTION_CONTEXT_CHARS,
        )

    def _build_conversation(
        self,
        events: list[MemoryEvent],
        task: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:

        messages: list[dict[str, Any]] = []

        seen_ids: set[Any] = set()

        for event in events:

            event_id = getattr(
                event,
                "id",
                None,
            )

            seen_ids.add(event_id)

            source = str(
                getattr(
                    event,
                    "source",
                    "",
                )
                or ""
            )

            content = getattr(
                event,
                "content",
                None,
            )

            metadata = getattr(
                event,
                "metadata",
                None,
            )

            if not isinstance(
                metadata,
                dict,
            ):
                metadata = {}

            if source == "user":

                text = str(content or "").strip()

                if text:

                    messages.append(
                        {
                            "role": "user",
                            "content": text,
                        }
                    )

            elif source == "assistant":

                message = self._assistant_message(
                    content=content,
                    metadata=metadata,
                )

                if message is not None:
                    messages.append(message)

            elif source == "tool" and isinstance(content, dict):

                tool_message = {
                    "role": "tool",
                    "tool_name": str(
                        content.get(
                            "name",
                            "",
                        )
                    ),
                    "content": self._tool_payload(content),
                }

                # New events carry the native provider tool-call ID.
                #
                # Old events may not have one. Preserve the previous
                # behavior instead of inventing an ID.
                tool_call_id = content.get("tool_call_id")

                if tool_call_id:

                    tool_message["tool_call_id"] = str(tool_call_id)

                messages.append(tool_message)

            # source == "agent" intentionally skipped.
            #
            # Tool-call information already lives inside the native
            # assistant["tool_calls"] message.

        if isinstance(task, dict):

            task_id = task.get("id")

            task_text = str(task.get("content") or "").strip()

            if task_text and task_id is not None and task_id not in seen_ids:

                messages.append(
                    {
                        "role": "user",
                        "content": task_text,
                    }
                )

        self._shrink_old_tool_results(messages)

        self._drop_old_thinking(messages)

        return messages

    def _assistant_message(
        self,
        content: Any,
        metadata: dict[str, Any],
    ) -> dict[str, Any] | None:
        """
        Reconstruct the assistant message while preserving provider
        protocol fields required for future tool calls.
        """

        raw = metadata.get("llm_message")

        if not isinstance(
            raw,
            dict,
        ):
            raw = {}

        message: dict[str, Any] = {
            "role": "assistant",
            "content": (raw.get("content") or content or ""),
        }

        tool_calls = raw.get("tool_calls")

        if tool_calls:

            message["tool_calls"] = tool_calls

        reasoning_details = raw.get("reasoning_details")

        if reasoning_details:

            message["reasoning_details"] = reasoning_details

        reasoning = raw.get("reasoning")

        if reasoning:

            message["reasoning"] = reasoning

        for key in (
            "refusal",
            "annotations",
            "audio",
        ):

            value = raw.get(key)

            if value is not None:
                message[key] = value

        thinking = raw.get("thinking") or metadata.get("thinking")

        if thinking:

            message["thinking"] = self._truncate(
                str(thinking),
                self.MAX_THINKING_CHARS,
            )

        if (
            not str(message.get("content") or "").strip()
            and "tool_calls" not in message
        ):
            return None

        return message

    def _tool_payload(
        self,
        event_content: dict[str, Any],
    ) -> str:
        """
        Render one tool result as bounded text.

        Structured fields remain JSON.
        Large textual fields are moved into raw blocks so the model
        receives readable newlines.
        """

        inner = event_content.get("content")

        if isinstance(
            inner,
            dict,
        ):

            payload = dict(inner)

        else:

            payload = {"message": str(inner)}

        payload["success"] = bool(event_content.get("success"))

        blocks: list[str] = []

        for key in self._TEXT_FIELDS:

            value = payload.get(key)

            if isinstance(
                value,
                str,
            ):

                payload.pop(key)

                if value.strip():

                    blocks.append(f"[{key}]\n{value}")

        files = payload.get("files")

        if isinstance(
            files,
            list,
        ):

            slim_files: list[dict[str, Any]] = []

            for item in files:

                if not isinstance(
                    item,
                    dict,
                ):
                    continue

                slim_files.append(
                    {
                        key: value
                        for key, value in item.items()
                        if key
                        not in (
                            "content",
                            "content_preview",
                        )
                    }
                )

                text = item.get("content")

                if (
                    isinstance(
                        text,
                        str,
                    )
                    and text.strip()
                ):

                    blocks.append(f"[file: " f"{item.get('path', '')}]\n" f"{text}")

            payload["files"] = slim_files

        text = json.dumps(
            payload,
            ensure_ascii=False,
            default=str,
        )

        if blocks:

            text = text + "\n\n" + "\n\n".join(blocks)

        if len(text) > self.MAX_TOOL_CHARS:

            text = text[: self.MAX_TOOL_CHARS] + "\n...[truncated]"

        return text

    def _shrink_old_tool_results(
        self,
        messages: list[dict[str, Any]],
    ) -> None:

        tool_positions = [
            index
            for index, message in enumerate(messages)
            if message.get("role") == "tool"
        ]

        if len(tool_positions) <= self.FULL_TOOL_RESULTS:
            return

        old_positions = tool_positions[: -self.FULL_TOOL_RESULTS]

        for index in old_positions:

            content = messages[index].get(
                "content",
                "",
            )

            if not isinstance(
                content,
                str,
            ):
                continue

            if len(content) > self.OLD_TOOL_CHARS:

                messages[index]["content"] = (
                    content[: self.OLD_TOOL_CHARS] + " ...[old result truncated]"
                )

    def _drop_old_thinking(
        self,
        messages: list[dict[str, Any]],
    ) -> None:
        """
        Keep detailed reasoning only after the latest user turn.

        Tool calls/results remain untouched because their protocol structure
        must stay intact.
        """

        last_user = self._last_index(
            messages,
            "user",
        )

        for index, message in enumerate(messages):

            if index < last_user:

                message.pop(
                    "thinking",
                    None,
                )

    def _populate_window(
        self,
        events: list[MemoryEvent],
        task: dict[str, Any] | None,
        workspace: str | None,
        agent_state: dict[str, Any] | None,
        progress: dict[str, Any] | None,
        working_set: dict[str, Any] | None,
        observation: dict[str, Any] | None,
        recent_actions: dict[str, Any] | None,
    ) -> None:

        self.window.set_system(self.system_instruction)

        self.window.set_runtime(workspace)

        # ContextWindow already owns the system/runtime section.
        #
        # Extend its runtime payload with the current execution snapshot
        # instead of creating another synthetic conversation message.
        #
        # This keeps the actual chat history protocol-native.
        execution_context = self._build_execution_context(
            task=task,
            agent_state=agent_state,
            progress=progress,
            working_set=working_set,
            observation=observation,
            recent_actions=recent_actions,
        )

        if execution_context:

            self.window.runtime["execution_context"] = execution_context

        self.window.set_conversation(
            self._build_conversation(
                events=events,
                task=task,
            )
        )

    def _fit_messages(
        self,
        messages: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """
        Keep the system message and the newest contiguous conversation slice.

        We never intentionally begin with an orphan tool message.

        Native assistant tool calls and their following tool results remain
        contiguous because history is trimmed only from the beginning.
        """

        system = [message for message in messages if message.get("role") == "system"][
            :1
        ]

        rest = [message for message in messages if message.get("role") != "system"]

        start = len(rest)

        for index in range(
            len(rest) - 1,
            -1,
            -1,
        ):

            candidate = system + rest[index:]

            if not self.tokenbudget.fits(candidate):
                break

            start = index

        # Never begin with an orphan tool result.
        while start < len(rest) and rest[start].get("role") == "tool":

            start += 1

        kept = rest[start:]

        # Make sure the current task remains visible.
        last_user = self._last_index(
            rest,
            "user",
        )

        if last_user != -1 and last_user < start:

            kept.insert(
                0,
                rest[last_user],
            )

        return system + kept

    def _minimal_messages(
        self,
    ) -> list[dict[str, Any]]:

        system = {
            "role": "system",
            "content": self.window.build_system_content(),
        }

        for message in reversed(self.window.conversation):

            if message.get("role") == "user":

                return [
                    system,
                    message,
                ]

        return [system]

    def build_context(
        self,
        events: list[MemoryEvent],
        task: dict[str, Any] | None = None,
        agent_state: dict[str, Any] | None = None,
        progress: dict[str, Any] | None = None,
        working_set: dict[str, Any] | None = None,
        observation: dict[str, Any] | None = None,
        recent_actions: dict[str, Any] | None = None,
        workspace: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Build the complete model-visible context.

        Includes:

            - system instruction
            - runtime/workspace
            - current task
            - agent state
            - progress
            - working set
            - observations
            - recent actions
            - native conversation/tool-call history

        When the full context exceeds the model token budget:

            1. Keep the full context when possible.
            2. Drop the oldest conversation history.
            3. Keep the newest contiguous tool-aware history.
            4. Fall back to system + newest user message.

        Memory retrieval itself remains outside this class: the `events`
        passed here are the memory/trajectory selected by the caller.
        """

        self._populate_window(
            events=events,
            task=task,
            workspace=workspace,
            agent_state=agent_state,
            progress=progress,
            working_set=working_set,
            observation=observation,
            recent_actions=recent_actions,
        )

        messages = self.window.get_prompt()

        if self.tokenbudget.fits(messages):
            return messages

        messages = self._fit_messages(messages)

        if self.tokenbudget.fits(messages):
            return messages

        return self._minimal_messages()
