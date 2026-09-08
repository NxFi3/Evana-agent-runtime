#src/Tools/ToolManager.py

from typing import Any
from src.Tools.ToolResult import ToolResult
from src.Tools.ToolDispatcher import ToolDispatcher
from src.Tools.ToolRegistry import ToolRegistry
from src.Utils.logger import get_logger

class ToolManager:

    def __init__(self) -> None:
        self.logger = get_logger('[TOOLMANAGER]')
        self.dispatcher = ToolDispatcher()
        self.toolregistry = ToolRegistry()

    def get_tools(self):
        self.toolregistry.discover()
        return self.toolregistry.get_definitions()

    def execute(self, tool_calls: list[Any]):
        calls = []
        results = []

        for tool_call in tool_calls:
            try:
                name, args = self.dispatcher.dispatch(tool_call)
                calls.append(
                    {
                        "name": name,
                        "arguments": args
                    }
                )

                tool = self.toolregistry.get(name)

                if tool is None:
                    results.append(
                        ToolResult(
                            success=False,
                            content=f"Tool not found: {name}"
                        )
                    )
                    continue

                results.append(tool.execute(**args))

            except Exception as e:
                self.logger.error(f"Tool execution error: {e}")

                results.append(
                    ToolResult(
                        success=False,
                        content=f"Tool execution error: {e}"
                    )
                )

        return {
            "calls": calls,
            "results": results
        }