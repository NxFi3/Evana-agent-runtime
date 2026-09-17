from __future__ import annotations

import json
import platform
from typing import Any

Message = dict[str, Any]


class ContextWindow:

    def __init__(self) -> None:

        self.os_name = platform.system()

        self.system_instruction: str = ""

        self.task: dict[str, Any] = {}

        self.agent_state: dict[str, Any] = {}

        self.progress: dict[str, Any] = {}

        self.runtime: dict[str, Any] = {
            "os": self.os_name,
        }

        self.conversation: list[Message] = []

    def set_system(
        self,
        instruction: str,
    ) -> None:

        self.system_instruction = (instruction or "").strip()

    def set_task(
        self,
        content: dict[str, Any],
    ) -> None:

        self.task = content or {}

    def set_agent_state(
        self,
        content: dict[str, Any],
    ) -> None:

        self.agent_state = content or {}

    def set_progress(
        self,
        content: dict[str, Any],
    ) -> None:

        self.progress = content or {}

    def set_runtime(
        self,
        workspace: str | None = None,
    ) -> None:

        self.runtime = {
            "os": self.os_name,
        }

        if workspace:
            self.runtime["workspace"] = workspace

    def set_conversation(
        self,
        content: list[Message],
    ) -> None:

        self.conversation = content or []

    @staticmethod
    def _serialize(
        content: Any,
    ) -> str:

        if isinstance(
            content,
            str,
        ):
            return content

        return json.dumps(
            content,
            ensure_ascii=False,
            indent=2,
            default=str,
        )

    @classmethod
    def _section(
        cls,
        name: str,
        content: Any,
    ) -> str:

        return f"<{name}>\n" f"{cls._serialize(content)}\n" f"</{name}>"

    def build_system_content(
        self,
    ) -> str:

        sections: list[str] = []

        if self.system_instruction:
            sections.append(self.system_instruction)

        if self.task:
            sections.append(
                self._section(
                    "task",
                    self.task,
                )
            )

        if self.agent_state:
            sections.append(
                self._section(
                    "agent_state",
                    self.agent_state,
                )
            )

        if self.progress:
            sections.append(
                self._section(
                    "progress",
                    self.progress,
                )
            )

        sections.append(
            self._section(
                "runtime",
                self.runtime,
            )
        )

        return "\n\n".join(sections)

    def get_prompt(
        self,
    ) -> list[Message]:

        messages: list[Message] = []

        system_content = self.build_system_content()

        if system_content:

            messages.append(
                {
                    "role": "system",
                    "content": system_content,
                }
            )

        messages.extend(self.conversation)

        return messages
