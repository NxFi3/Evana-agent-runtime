#src/Engine/providers/ProviderBase.py

from abc import ABC, abstractmethod
from ast import Dict
from typing import ClassVar
from src.Engine.providers.LLMResult import LLMResult 
from src.Engine.providers.LLMInput import LLMInput

class ProviderBase(ABC):
    """
    Base interface for all Providers.

    """
    name:  ClassVar[str] = ""
    defaultModel: ClassVar[str] = ""
    defaultConfig:dict
    @abstractmethod
    def generate(self,call:LLMInput) -> LLMResult:
        """
        generate llmresult.

        Arguments are provided as keyword arguments and should be
        validated by the concrete provider.
        """
        raise NotImplementedError

    def __repr__(self) -> str:
        return f"<provider name='{self.name}'>"

