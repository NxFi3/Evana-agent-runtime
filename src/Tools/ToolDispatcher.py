# src/Tools/ToolDispatcher.py

import json
from src.Utils.logger import get_logger


class ToolDispatcher:

    def __init__(self):
        self.logger = get_logger('[DISPATCHER]')

    def dispatch(self, tool_call):
        # Native object format
        if hasattr(tool_call, "function"):
            function = tool_call.function

            name = getattr(function, "name", None)
            arguments = getattr(function, "arguments", {})

        # Dictionary format
        elif isinstance(tool_call, dict):
            function = tool_call.get("function", {})

            name = function.get("name")
            arguments = function.get("arguments", {})

        else:
            self.logger.warning(
                "Invalid tool call format."
            )
            raise TypeError("Invalid tool call format.")

        if not name:
            self.logger.warning(
                "Tool call is missing tool name."
            )
            raise ValueError(
                "Tool call is missing tool name."
            )

        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments)
            except json.JSONDecodeError as e:
                self.logger.warning(
                    f"Invalid tool arguments JSON: {e}"
                )
                raise ValueError(
                    f"Invalid tool arguments JSON: {e}"
                )

        if not isinstance(arguments, dict):
            self.logger.warning(
                "Tool arguments must be an object."
            )
            raise TypeError(
                "Tool arguments must be an object."
            )

        return name, arguments

