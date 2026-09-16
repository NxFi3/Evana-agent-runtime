import json
import platform
from typing import Any

Message = dict[str, Any]


class ContextWindow:

    def __init__(self) -> None:
        self.os_name = platform.system()

        self.system_instruction: str = ""

        self.task: dict[str, Any] = {}
        self.active_skills: dict[str, Any] = {}
        self.agent_state: dict[str, Any] = {}
        self.progress: dict[str, Any] = {}

        self.last_action: dict[str, Any] = {}
        self.last_observation: dict[str, Any] = {}

        self.conversation: list[Message] = []

    def set_system(
        self,
        instruction: str,
    ) -> None:
        self.system_instruction = instruction.strip()

    def set_task(
        self,
        content: dict[str, Any],
    ) -> None:
        self.task = content

    def set_active_skills(
        self,
        content: dict[str, Any],
    ) -> None:
        self.active_skills = content

    def set_agent_state(
        self,
        content: dict[str, Any],
    ) -> None:
        self.agent_state = content

    def set_progress(
        self,
        content: dict[str, Any],
    ) -> None:
        self.progress = content

    def set_last_action(
        self,
        content: dict[str, Any],
    ) -> None:
        self.last_action = content

    def set_last_observation(
        self,
        content: dict[str, Any],
    ) -> None:
        self.last_observation = content

    def set_conversation(
        self,
        content: list[Message],
    ) -> None:
        self.conversation = content

    @staticmethod
    def _serialize(
        content: dict[str, Any],
    ) -> str:
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
        content: dict[str, Any],
    ) -> str:
        return f"<{name}>\n" f"{cls._serialize(content)}\n" f"</{name}>"

    def get_prompt(self) -> list[Message]:
        messages: list[Message] = []

        system_sections: list[str] = []

        if self.system_instruction:
            system_sections.append(self.system_instruction)

        if self.task:
            system_sections.append(
                self._section(
                    "task",
                    self.task,
                )
            )

        if self.active_skills:
            system_sections.append(
                self._section(
                    "active_skills",
                    self.active_skills,
                )
            )

        if self.agent_state:
            system_sections.append(
                self._section(
                    "agent_state",
                    self.agent_state,
                )
            )

        if self.progress:
            system_sections.append(
                self._section(
                    "progress",
                    self.progress,
                )
            )

        if self.last_action:
            system_sections.append(
                self._section(
                    "last_action",
                    self.last_action,
                )
            )

        if self.last_observation:
            system_sections.append(
                self._section(
                    "last_observation",
                    self.last_observation,
                )
            )

        system_sections.append(
            self._section(
                "runtime",
                {
                    "os": self.os_name,
                },
            )
        )

        if system_sections:
            messages.append(
                {
                    "role": "system",
                    "content": "\n\n".join(system_sections),
                }
            )

        messages.extend(self.conversation)

        return messages
