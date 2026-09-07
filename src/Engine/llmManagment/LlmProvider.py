#src/Engine/llmManagment/LlmProvider.py
from src.Engine.llmManagment.ollama import OllamaProvider
from src.Utils.logger import get_logger
import numpy as np

logger = get_logger("[LLM]")

class LlmProvider:
    def __init__(self, config) -> None:
        llm_config = config.get("llm") or {}
        self.provider_type = llm_config.get("provider","ollama")
        self.llm_config = llm_config.get("provider_config") or {"model_name": "gpt-oss:20b"}
        self.LoadProviderModel()
    def LoadProviderModel(self):
        if self.provider_type == "ollama":
            self.model = OllamaProvider(self.llm_config)
        else:
            raise ValueError(f"Unsupported LLM provider: {self.provider_type}")
    def show_model_info(self):
        if self.provider_type == "ollama":
            return self.model.show_model_info()
        else:
            raise ValueError(f"Unsupported LLM provider: {self.provider_type}")
    def generate(self,text: str,tools:list = None,image: np.ndarray = None):
        return self.model.chat(text,tools, image)
