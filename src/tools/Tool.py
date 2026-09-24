from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, ClassVar

from src.models.ToolResult import ToolResult


class Tool(ABC):

    name: ClassVar[str] = ""

    description: ClassVar[str] = ""

    parameters: ClassVar[dict[str, Any]] = {
        "type": "object",
        "properties": {},
        "additionalProperties": True,
    }

    # Default semantic action for new tools.
    action: ClassVar[str] = "execute"

    @abstractmethod
    def execute(
        self,
        **kwargs: Any,
    ) -> ToolResult:
        raise NotImplementedError

    def validate(
        self,
        arguments: dict[str, Any],
    ) -> bool:
        """
        Optional lightweight validation hook.

        Concrete tools can override this.
        """
        return True

    def describe_call(
        self,
        arguments: dict[str, Any],
    ) -> dict[str, str]:
        """
        Return semantic information about a tool call.

        This method is intentionally generic so AgentState does not need
        to know concrete tool names.

        New tools can simply define:

            action = "search"

        and optionally override this method when they need a richer target.
        """

        if not isinstance(
            arguments,
            dict,
        ):
            arguments = {}

        return {
            "action": self.action,
            "target": self._infer_target(arguments),
        }

    @staticmethod
    def _infer_target(
        arguments: dict[str, Any],
    ) -> str:

        for key in (
            "file_path",
            "path",
            "url",
            "query",
            "command",
            "workdir",
        ):

            value = arguments.get(key)

            if value is None:
                continue

            if isinstance(
                value,
                list,
            ):
                return " ".join(str(item) for item in value).strip()

            return str(value).strip()

        return ""

    def get_definition(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    def __repr__(self) -> str:
        return f"<Tool name='{self.name}'>"
