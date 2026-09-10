import platform
from typing import Any, Dict, List


Message = Dict[str, Any]


class ContextWindow:
    def __init__(self):
        self.os_name = platform.system()
        self.system = ""
        self.task = ""
        self.trajectory: List[Message] = []
        self.plans = ""
        self.user = ""

    def set_system(self, content: str):
        self.system = content or ""

    def set_task(self, content: str):
        self.task = content or ""

    def set_trajectory(self, content: List[Message]):
        self.trajectory = list(content or [])

    def set_plans(self, content: str):
        self.plans = content or ""

    def set_user(self, content: str):
        self.user = content or ""

    def prompt(self) -> List[Message]:
        messages: List[Message] = []
        system_content = f"OS: {self.os_name}\n{self.system}".strip()
        if system_content:
            messages.append({"role": "system", "content": system_content})
        if self.task:
            messages.append({"role": "developer", "content": self.task})
        if self.plans:
            messages.append({"role": "assistant", "content": self.plans})
        messages.extend(self.trajectory)
        if self.user:
            messages.append({"role": "user", "content": self.user})
        return messages
