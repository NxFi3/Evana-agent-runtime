import json
import platform
from typing import Any

Message = dict[str, Any]


class ContextWindow:

    def __init__(self):
        self.os_name = platform.system()

        self.system: dict = {}
        self.task: dict = {}
        self.active_skills: dict = {}
        self.agent_state: dict = {}
        self.progress: dict = {}
        self.last_action: dict = {}
        self.last_observation: dict = {}

        self.conversation: list[Message] = []

    def set_system(
        self,
        content: dict,
    ) -> None:
        self.system = {
            **content,
            "os": self.os_name,
        }

    def set_task(
        self,
        content: dict,
    ) -> None:
        self.task = content

    def set_active_skills(
        self,
        content: dict,
    ) -> None:
        self.active_skills = content

    def set_agent_state(
        self,
        content: dict,
    ) -> None:
        self.agent_state = content

    def set_progress(
        self,
        content: dict,
    ) -> None:
        self.progress = content

    def set_last_action(
        self,
        content: dict,
    ) -> None:
        self.last_action = content

    def set_last_observation(
        self,
        content: dict,
    ) -> None:
        self.last_observation = content

    def set_conversation(
        self,
        content: list[Message],
    ) -> None:
        self.conversation = content

    @staticmethod
    def _serialize(
        content: dict,
    ) -> str:
        return json.dumps(
            content,
            ensure_ascii=False,
            indent=2,
            default=str,
        )

    @staticmethod
    def _build_system_message(
        section: str,
        content: dict,
    ) -> Message:
        return {
            "role": "system",
            "content": (
                f"<{section}>\n"
                f"{ContextWindow._serialize(content)}\n"
                f"</{section}>"
            ),
        }

    def get_prompt(self) -> list[Message]:
        messages: list[Message] = []

        if self.system:
            messages.append(
                self._build_system_message(
                    "system",
                    self.system,
                )
            )

        if self.task:
            messages.append(
                self._build_system_message(
                    "task",
                    self.task,
                )
            )

        if self.active_skills:
            messages.append(
                self._build_system_message(
                    "active_skills",
                    self.active_skills,
                )
            )

        if self.agent_state:
            messages.append(
                self._build_system_message(
                    "agent_state",
                    self.agent_state,
                )
            )

        if self.progress:
            messages.append(
                self._build_system_message(
                    "progress",
                    self.progress,
                )
            )

        if self.last_action:
            messages.append(
                self._build_system_message(
                    "last_action",
                    self.last_action,
                )
            )

        if self.last_observation:
            messages.append(
                self._build_system_message(
                    "last_observation",
                    self.last_observation,
                )
            )

        if self.conversation:
            messages.extend(self.conversation)

        return messages
