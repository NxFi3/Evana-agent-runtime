#src/Tools/Tool.py

from abc import ABC, abstractmethod
from typing import Any, Dict


class Tool(ABC):
    """
    Base interface for all tools.

    Every tool must provide:
        - name
        - description
        - parameters
        - execute()
    """

    name: str = ""
    description: str = ""
    parameters: Dict[str, Any] = {}

    @abstractmethod
    def execute(self, **kwargs) -> Any:
        """
        Execute the tool.

        Arguments are provided as keyword arguments and should be
        validated by the concrete tool.

        Example:
            tool.execute(query="latest Python release")
        """
        raise NotImplementedError

    def get_definition(self) -> Dict[str, Any]:
        """
        Return the tool definition used by the agent/LLM.
        """

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

