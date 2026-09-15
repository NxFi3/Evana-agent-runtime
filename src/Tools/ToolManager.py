from typing import Any

from src.Tools.ToolResult import ToolResult
from src.Tools.ToolDispatcher import ToolDispatcher
from src.Tools.ToolRegistry import ToolRegistry
from src.Utils.logger import get_logger


class ToolManager:

    def __init__(self) -> None:
        self.logger = get_logger("[TOOLMANAGER]")

        self.dispatcher = ToolDispatcher()
        self.toolregistry = ToolRegistry()

        self._definitions: list[dict] | None = None

    def get_tools(self):
        """
        Discover builtin tools once and return their definitions.
        """

        if self._definitions is None:
            self.toolregistry.discover()
            self._definitions = self.toolregistry.get_definitions()

        return self._definitions

    def _find_definition(
        self,
        name: str,
    ) -> dict | None:
        normalized_name = str(name).strip().lower()

        for definition in self.get_tools():
            if not isinstance(definition, dict):
                continue

            function = definition.get("function", {})

            if not isinstance(function, dict):
                continue

            definition_name = str(function.get("name", "")).strip().lower()

            if definition_name == normalized_name:
                return definition

        return None

    def _find_tool(
        self,
        name: str,
    ):
        return self.toolregistry.get(str(name).strip().lower())

    def _call_metadata(
        self,
        parsed: dict,
    ) -> dict:
        return {
            "tool_name": parsed.get("name", ""),
            "tool_call_id": parsed.get("id"),
            "tool_call_type": parsed.get("type", "function"),
        }

    def execute(
        self,
        tool_calls: list[Any],
    ):
        calls = []
        results = []

        if not tool_calls:
            return {
                "calls": [],
                "results": [],
            }

        for tool_call in tool_calls:

            # Always preserve the original call for history.
            calls.append(tool_call)

            raw_name = ""

            try:
                if hasattr(tool_call, "function"):
                    raw_name = getattr(
                        tool_call.function,
                        "name",
                        "",
                    )
                elif isinstance(tool_call, dict):
                    function = tool_call.get(
                        "function",
                        {},
                    )

                    if isinstance(function, dict):
                        raw_name = function.get(
                            "name",
                            "",
                        )

                raw_name = str(raw_name or "").strip()

            except Exception:
                raw_name = ""

            # First parse without execution.
            definition = self._find_definition(raw_name) if raw_name else None

            parsed = self.dispatcher.dispatch(
                tool_call,
                tool_definition=definition,
            )

            metadata = self._call_metadata(parsed)

            # ------------------------------------------------------------------
            # Invalid model-generated call
            # ------------------------------------------------------------------
            if not parsed.get("valid", False):

                error = parsed.get(
                    "error",
                    "Invalid tool call.",
                )

                self.logger.warning(
                    f"Rejected tool call " f"'{parsed.get('name', raw_name)}': {error}"
                )

                results.append(
                    ToolResult(
                        success=False,
                        content=(f"Tool call rejected: {error}"),
                        metadata={
                            **metadata,
                            "error_type": "validation_error",
                            "tool_call_valid": False,
                        },
                    )
                )

                continue

            name = str(parsed.get("name", "")).strip()

            args = parsed.get(
                "arguments",
                {},
            )

            # ------------------------------------------------------------------
            # Unknown tool
            # ------------------------------------------------------------------
            tool = self._find_tool(name)

            if tool is None:

                error = f"Tool not found: {name}"

                self.logger.warning(error)

                results.append(
                    ToolResult(
                        success=False,
                        content=error,
                        metadata={
                            **metadata,
                            "error_type": "tool_not_found",
                            "tool_call_valid": True,
                        },
                    )
                )

                continue

            # ------------------------------------------------------------------
            # Execution
            # ------------------------------------------------------------------
            try:

                self.logger.info(f"Executing {name} -> {args}")

                result = tool.execute(**args)

                if isinstance(result, ToolResult):
                    # Preserve runtime metadata and attach call metadata.
                    result.metadata = {
                        **metadata,
                        **(result.metadata if result.metadata else {}),
                        "tool_call_valid": True,
                    }

                    results.append(result)

                else:
                    # Defensive normalization for tools that return raw values.
                    results.append(
                        ToolResult(
                            success=True,
                            content=str(result),
                            metadata={
                                **metadata,
                                "tool_call_valid": True,
                                "normalized_result": True,
                            },
                        )
                    )

            except TypeError as exc:

                self.logger.warning(f"Tool argument error in '{name}': {exc}")

                results.append(
                    ToolResult(
                        success=False,
                        content=(f"Tool argument error: {exc}"),
                        metadata={
                            **metadata,
                            "error_type": "argument_error",
                            "tool_call_valid": True,
                        },
                    )
                )

            except Exception as exc:

                self.logger.error(f"Tool execution error in '{name}': {exc}")

                results.append(
                    ToolResult(
                        success=False,
                        content=(f"Tool execution error: {exc}"),
                        metadata={
                            **metadata,
                            "error_type": "execution_error",
                            "tool_call_valid": True,
                        },
                    )
                )

        return {
            "calls": calls,
            "results": results,
        }
