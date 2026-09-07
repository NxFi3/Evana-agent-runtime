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

    def getTools(self):
        self.toolregistry.discover()
        return self.toolregistry.get_definitions()

    def execute(self, arguments: list[Any]):
        results = []

        for argument in arguments:
            try:
                name, args = self.dispatcher.dispatch(argument)

                tool = self.toolregistry.get(name)

                if tool is None:
                    results.append(
                        ToolResult(
                            success=False,
                            content=f"Tool not found: {name}"
                        )
                    )
                    continue

                result = tool.execute(**args)
                results.append(result)

            except Exception as e:
                self.logger.error(f"Tool execution error: {e}")
                results.append(ToolResult(success=False,content=f"Tool execution error: {e}"))

        return results