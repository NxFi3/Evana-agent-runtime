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

        # Keep workspace inventory bounded.
        self.max_workspace_files = 300

    def set_system(
        self,
        content: str,
    ):
        self.system = content or ""

    def set_skills(
        self,
        content: str,
    ):
        self.skills = content or ""

    def set_user(
        self,
        content: str,
    ):
        self.user = content or ""

    def set_task(
        self,
        content: str,
    ):
        self.task = content or ""

    def set_agent_state(
        self,
        content: str,
    ):
        self.agent_state = content or ""

    def set_workspace(
        self,
        root: str,
        state: str = "",
    ):
        self.workspace_root = root or ""
        self.workspace_state = state or ""

    def set_workspace_files(
        self,
        files: List[str],
    ):
        self.workspace_files = sorted(str(path) for path in (files or []))

    def set_history(
        self,
        content: List[Message],
    ):
        self.history = list(content or [])

    def set_compacted_history(
        self,
        content: List[Message],
    ):
        self.compacted_history = list(content or [])

    def set_last_action(
        self,
        content: str,
    ):
        self.last_action = content or ""

    def set_last_observation(
        self,
        content: str,
    ):
        self.last_observation = content or ""

    def _workspace_message(
        self,
    ) -> str:
        parts = []

        if self.workspace_root:
            parts.append(f"Workspace: {self.workspace_root}")

        if self.workspace_state:
            parts.append("Workspace state:\n" + self.workspace_state)

        if self.workspace_files:

            files = self.workspace_files

            truncated = False

            if len(files) > self.max_workspace_files:
                files = files[: self.max_workspace_files]
                truncated = True

            inventory = "\n".join(f"- {path}" for path in files)

            if truncated:
                inventory += (
                    "\n"
                    "... "
                    f"[{len(self.workspace_files) - len(files)} "
                    "more files omitted]"
                )

            parts.append("Workspace files:\n" + inventory)

        return "\n\n".join(parts)

    def prompt(self) -> List[Message]:

        messages: List[Message] = []

        if self.system:

            messages.append(
                {
                    "role": "system",
                    "content": (f"OS: {self.os_name}\n" f"{self.system}"),
                }
            )

        if self.skills:

            messages.append(
                {
                    "role": "system",
                    "content": ("Skills you must know:\n" f"{self.skills}"),
                }
            )

        if self.agent_state:

            messages.append(
                {
                    "role": "system",
                    "content": self.agent_state,
                }
            )

        if self.user:

            messages.append(
                {
                    "role": "user",
                    "content": self.user,
                }
            )

        workspace_message = self._workspace_message()

        if workspace_message:

            messages.append(
                {
                    "role": "system",
                    "content": workspace_message,
                }
            )

        if self.task:

            messages.append(
                {
                    "role": "system",
                    "content": ("Current task:\n" f"{self.task}"),
                }
            )

        if self.last_action:

            messages.append(
                {
                    "role": "system",
                    "content": ("Last action:\n" f"{self.last_action}"),
                }
            )

        if self.last_observation:

            messages.append(
                {
                    "role": "system",
                    "content": ("Last observation:\n" f"{self.last_observation}"),
                }
            )

        if self.compacted_history:

            messages.extend(self.compacted_history)

        if self.history:

            messages.extend(self.history)

        return messages
