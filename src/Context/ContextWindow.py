# src/Context/ContextWindow.py

import platform
from typing import Any, Dict, List


Message = Dict[str, Any]


class ContextWindow:

    def __init__(self):

        self.os_name = platform.system()
        self.system = ""
        self.skills = ""
        self.user = ""
        self.task = ""
        self.agent_state = ""
        self.workspace_root = ""
        self.workspace_state = ""
        self.workspace_files: List[str] = []
        self.history: List[Message] = []
        self.compacted_history: List[Message] = []
        self.last_action = ""
        self.last_observation = ""

  
    def set_system(self, content: str):
        self.system = content or ""

    def set_skills(self, content: str):
        self.skills = content or ""

    def set_user(self, content: str):
        self.user = content or ""

    def set_task(self, content: str):
        self.task = content or ""

    def set_agent_state(self, content: str):
        self.agent_state = content or ""

    def set_workspace(
        self,
        root: str,
        state: str = ""
    ):
        self.workspace_root = root or ""
        self.workspace_state = state or ""

    def set_workspace_files(
        self,
        files: List[str]
    ):
        self.workspace_files = list(files or [])

    def set_history(
        self,
        content: List[Message]
    ):
        self.history = list(content or [])

    def set_compacted_history(
        self,
        content: List[Message]
    ):
        self.compacted_history = list(content or [])

    def set_last_action(
        self,
        content: str
    ):
        self.last_action = content or ""

    def set_last_observation(
        self,
        content: str
    ):
        self.last_observation = content or ""

    def prompt(self) -> List[Message]:

        messages: List[Message] = []

        if self.system:

            messages.append({
                "role": "system",
                "content": (
                    f"OS: {self.os_name}\n"
                    f"{self.system}"
                )
            })

        if self.skills:

            messages.append({
                "role": "system",
                "content": (
                    "Skills you must know:\n"
                    f"{self.skills}"
                )
            })

        if self.agent_state:

            messages.append({
                "role": "system",
                "content": self.agent_state
            })

        if self.user:

            messages.append({
                "role": "user",
                "content": self.user
            })

        if self.task:

            messages.append({
                "role": "system",
                "content": (
                    "Current task:\n"
                    f"{self.task}"
                )
            })


        if (
            self.workspace_root
            or self.workspace_files
            or self.workspace_state
        ):

            workspace_parts = []

            if self.workspace_root:

                workspace_parts.append(
                    f"Workspace root: "
                    f"{self.workspace_root}"
                )

            if self.workspace_files:

                workspace_parts.append(
                    "Workspace files:\n"
                    + "\n".join(
                        self.workspace_files
                    )
                )

            if self.workspace_state:

                workspace_parts.append(
                    "Workspace state:\n"
                    + self.workspace_state
                )

            messages.append({
                "role": "system",
                "content": "\n\n".join(
                    workspace_parts
                )
            })


        if self.compacted_history:

            messages.extend(
                self.compacted_history
            )

        if self.history:

            messages.extend(
                self.history
            )

        if self.last_action:

            messages.append({
                "role": "assistant",
                "content": self.last_action
            })

        if self.last_observation:

            messages.append({
                "role": "tool",
                "content": self.last_observation
            })

        return messages