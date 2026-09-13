import platform
from typing import Any, Dict, List

Message = Dict[str, Any]


class ContextWindow:
    def __init__(self):
        self.os_name = platform.system()
        self.system = ""
        self.task = ""
        self.workspace_root = ""
        self.workspace_state = ""
        self.trajectory: List[Message] = []
        self.plans = ""
        self.user = ""

    def set_system(self, content: str):
        self.system = content or ""

    def set_task(self, content: str):
        self.task = content or ""

    def set_workspace(self, root: str, state: str = ""):
        self.workspace_root = root or ""
        self.workspace_state = state or ""

    def set_trajectory(self, content: List[Message]):
        self.trajectory = list(content or [])

    def set_plans(self, content: str):
        self.plans = content or ""

    def set_user(self, content: str):
        self.user = content or ""

    def prompt(self) -> List[Message]:
        messages: List[Message] = []
        system_parts = [f"OS: {self.os_name}",self.system,self.task]

        if self.workspace_root:
            system_parts.append(f"WORKSPACE ROOT: {self.workspace_root}")

        if self.workspace_state:
            system_parts.append(f"WORKSPACE STATE:\n{self.workspace_state}")
        system_content = "\n\n".join(part.strip() for part in system_parts if part and part.strip())

        if system_content:
            messages.append({"role": "system","content": system_content})

        if self.user:
            messages.append({"role": "user","content": self.user})
        if self.plans:
            messages.append({"role": "assistant","content": self.plans})

        messages.extend(self.trajectory)
        return messages