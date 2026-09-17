from typing import Any

from src.models.ToolResult import ToolResult
from src.tools.ToolDispatcher import ToolDispatcher
from src.tools.ToolRegistry import ToolRegistry
from src.utils.logger import get_logger
from src.security.securityService import security  # NotImplemented


class ToolManager:

    def __init__(self) -> None:
        self.logger = get_logger("[TOOLMANAGER]")
        self.toolregistry = ToolRegistry()
        self.dispatcher = ToolDispatcher(self.toolregistry)
        self.security = security()
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

    def execute(self, tool_calls):
        calls = []
        results = []

        if not tool_calls:
            return {"calls": [], "results": []}

        try:
            parsed_tool_calls = self.dispatcher.dispatch(tool_calls)
        except Exception as e:
            self.logger.error(f"dispatch failed: {e}")
            return {"calls": [], "results": []}

        for toolcall in parsed_tool_calls:
            calls.append(toolcall)
            if not toolcall.valid:
                results.append(
                    ToolResult(
                        success=False,
                        name=toolcall.name,
                        content={
                            "success": False,
                            "content": "Invalid tool call.",
                        },
                        metadata={},
                    )
                )
                continue
            tool = self._find_tool(toolcall.name.lower())

            if tool is None:
                results.append(
                    ToolResult(
                        success=False,
                        name=toolcall.name,
                        content={
                            "success": False,
                            "content": "Tool Not Found.",
                        },
                        metadata={},
                    )
                )
                continue

            toolcall = self.security.check(toolcall)

            if not toolcall.approved:
                results.append(
                    ToolResult(
                        success=False,
                        name=toolcall.name,
                        content={
                            "success": False,
                            "content": "You are not allowed to use this tool.",
                        },
                        metadata={},
                    )
                )
                continue

            try:
                result = tool.execute(**toolcall.args)
                results.append(result)
            except Exception as e:
                self.logger.error(f"tool '{toolcall.name}' failed: {e}")
                results.append(
                    ToolResult(
                        success=False,
                        name=toolcall.name,
                        content={
                            "success": False,
                            "content": f"unexpected error while using tool: {e}",
                        },
                        metadata={},
                    )
                )

        return {"calls": calls, "results": results}
