# src/Tools/ToolDispatcher.py

import json
from typing import Any

from src.models.ToolCall import ToolCall


class ToolDispatcher:

    def __init__(self, tool_registry):
        self.tool_registry = tool_registry

    def dispatch(self, raw_calls: dict | list[dict]) -> list[ToolCall]:
        """
        Parse and validate one or multiple LLM tool calls.

        Input:
            dict      -> single tool call
            list[dict] -> multiple tool calls

        Output:
           list[ToolCall].
        """

        if isinstance(raw_calls, dict):
            raw_calls = [raw_calls]

        if not isinstance(raw_calls, list):
            return [ToolCall(name="", valid=False)]

        return [self._dispatch_call(raw_call) for raw_call in raw_calls]

    def _dispatch_call(self, raw_call: Any) -> ToolCall:

        try:
            if not isinstance(raw_call, dict):
                return ToolCall(name="", valid=False)

            name = raw_call.get("name")
            arguments = raw_call.get("arguments", {})

            if not isinstance(name, str) or not name:
                return ToolCall(name="", valid=False)

            if isinstance(arguments, str):
                try:
                    arguments = json.loads(arguments)
                except (json.JSONDecodeError, TypeError):
                    return ToolCall(
                        name=name,
                        valid=False,
                    )

            if not isinstance(arguments, dict):
                return ToolCall(
                    name=name,
                    valid=False,
                )

            if name not in self.tool_registry:
                return ToolCall(
                    name=name,
                    args=arguments,
                    valid=False,
                )

            tool = self.tool_registry[name]

            if hasattr(tool, "validate"):
                if tool.validate(arguments) is False:
                    return ToolCall(
                        name=name,
                        args=arguments,
                        valid=False,
                    )

            return ToolCall(
                name=name,
                args=arguments,
                valid=True,
            )

        except Exception:
            return ToolCall(
                name="",
                valid=False,
            )
