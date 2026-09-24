from __future__ import annotations

import json
import platform
from pathlib import Path
from typing import Any

Message = dict[str, Any]


class ContextWindow:
    """
    Model-visible prompt = ONE stable system message + the real chat history.

    The system message contains only the static instruction and the runtime
    info (os / cwd / workspace). Everything that changes between iterations
    (user turns, assistant turns, tool calls, tool results) lives in the
    message list, so the model sees a normal chat and Ollama can reuse the
    prompt prefix instead of re-processing everything on every iteration.
    """

    def __init__(self) -> None:

        self.os_name = platform.system()

        self.system_instruction: str = ""

        self.runtime: dict[str, Any] = {
            "os": self.os_name,
            "cwd": str(Path.cwd()),
        }

        self.conversation: list[Message] = []

    def set_system(
        self,
        instruction: str,
    ) -> None:
        self.system_instruction = (instruction or "").strip()

    def set_runtime(
        self,
        workspace: str | None = None,
    ) -> None:

        self.runtime = {
            "os": self.os_name,
            "cwd": str(Path.cwd()),
        }

        if workspace:
            self.runtime["workspace"] = str(Path(workspace).expanduser().resolve())

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
