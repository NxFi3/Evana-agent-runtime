#src/Engine/llmManagment/ollama.py

import ollama
from src.Utils.logger import get_logger
import numpy as np

logger = get_logger("[Ollama]")
class OllamaProvider:

    def __init__(self, config: dict) -> None:
        self.default_model = "gpt-oss:20b"
        self.config = config

        self.model_name = (config.get("model_name")or self.default_model)
        model_context_length = self.get_model_context_length()

        self.options = {
            "temperature": 0.7,
            "repetition_penalty": 1.1,
        }

        if model_context_length is not None:
            self.options["num_ctx"] = model_context_length

        self.options.update(
            config.get("llm-options") or {}
        )

        logger.info(f"Using Ollama model: {self.model_name}")
        logger.info(f"Ollama options: {self.options}")

    def show_model_info(self):
        try:
            model_info = ollama.show(self.model_name)
            logger.info(f"Model info: {model_info}")
            return model_info

        except Exception as e:
            logger.error(f"Error fetching model info: {e}")
            return None

    def get_model_context_length(self):
        try:
            model_info = self.show_model_info()
            if model_info is None:
                return None
            for key, value in model_info.modelinfo.items():
                if key.endswith(".context_length"):
                    return value
            logger.warning(f"Context length not found for model: {self.model_name}")
            return None
        except Exception as e:
            logger.error(f"Error fetching model context length: {e}")
            return None

    def generate(self, text: str, image: np.ndarray = None):
        try:
            logger.info("Generating text")
            if image is not None:
                result = ollama.generate(model=self.model_name,prompt=text,options=self.options,images=image)
            else:
                result = ollama.generate(model=self.model_name,prompt=text,options=self.options)
            return result

        except Exception as e:
            logger.error(f"Generation error: {e}")
            return {}