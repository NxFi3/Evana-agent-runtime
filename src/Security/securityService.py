# NotImplemented

from src.models.ToolCall import ToolCall


class security:
    def __init__(self) -> None:
        pass

    def check(self, toolcall: ToolCall):
        toolcall.approved = True
        return toolcall
