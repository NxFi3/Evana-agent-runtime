# NotImplemented

from src.models.ToolCall import ToolCall


class security:
    def __init__(self) -> None:
        self.force_approve = False

    def check(self, toolcall: ToolCall):
        toolcall.approved = False
        if self.force_approve:
            toolcall.approved = True
        return toolcall
