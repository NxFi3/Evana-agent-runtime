#src/Tools/ToolRegistry.py
from pathlib import Path
import importlib
import inspect
from src.Utils.logger import get_logger
from src.Tools.Tool import Tool


class ToolRegistry:

    def __init__(self):
        self.tools_path = Path(__file__).parent / "builtin"
        self.logger = get_logger('[TOOLREGISTRY]')
        self.tools = {}
    def _discover_tools(self):

        discovered_tools = []

        for item in self.tools_path.iterdir():

            if not item.is_dir():
                continue

            if item.name.startswith("_"):
                continue

            self.logger.info(f"Found tool package: {item.name}")
            module_name = f"src.Tools.builtin.{item.name}"

            try:
                module = importlib.import_module(module_name)

            except Exception as e:
                self.logger.error(
                    f"Failed to load tool package "
                    f"'{item.name}': {e}"
                )
                continue

            self.logger.info(f"Loaded module: {module}")

            if not hasattr(module, "__all__"):
                self.logger.warning(
                    f"Skipping '{item.name}': "
                    f"__all__ not found"
                )
                continue

            self.logger.info(f"Exports: {module.__all__}")

            for export_name in module.__all__:
                obj = getattr(module, export_name, None)

                if obj is None:
                    self.logger.warning(
                        f"Skipping '{export_name}': "
                        f"not found in module"
                    )
                    continue

                if not inspect.isclass(obj):
                    self.logger.warning(
                        f"Skipping '{export_name}': "
                        f"not a class"
                    )
                    continue
                if not issubclass(obj, Tool):
                    self.logger.warning(
                        f"Skipping '{export_name}': "
                        f"not a Tool"
                    )
                    continue

                if inspect.isabstract(obj):
                    self.logger.warning(
                        f"Skipping '{export_name}': "
                        f"Tool is abstract"
                    )
                    continue

                self.logger.info(f"Found Tool class: {obj}")
                try:
                    tool = obj()

                except Exception as e:
                    self.logger.error(
                        f"Failed to instantiate "
                        f"'{export_name}': {e}"
                    )
                    continue

                self.logger.info(
                    f"Instantiated: "
                    f"{tool.name}"
                )

                discovered_tools.append(tool)

        return discovered_tools


    def discover(self):
        discovered_tools = self._discover_tools()

        for tool in discovered_tools:
            self.tools[tool.name] = tool

        self.logger.info(
            f"Discovered {len(discovered_tools)} tool(s)"
        )


    def is_available(self,toolname:str):
        return toolname in self.tools
    def get(self, toolname: str):
        return self.tools.get(toolname)
        
    def get_definitions(self):
        return [tool.get_definition() for tool in self.tools.values()]