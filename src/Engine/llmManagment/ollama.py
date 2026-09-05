#src/Engine/llmManagment/ollama.py
import ollama
from src.Utils.logger import get_logger
import numpy as np 
logger = get_logger("[Ollama]")


class OllamaProvider:

    def __init__(self, config: dict) -> None:
        self.default_model = "gpt-oss:20b"
        self.config = config
        self.model_name = (
            config.get("model_name")
            or self.default_model
        )
        self.options = config.get("llm-options") or {
            "temperature": 0.7,
            "repetition_penalty": 1.1,
        }
        logger.info(f"Using Ollama model: {self.model_name}")
    def generate(self, text: str, image: np.ndarray = None):
        try:
            logger.info("Generating text")

            if image is not None:
                result = ollama.generate(model=self.model_name,prompt=text,options=self.options,images=image)
            else:
                result = ollama.generate(model=self.model_name,prompt=text,options=self.options)

            return str(result.get(
                "response",
                "NO_RESPONSE")
            )

        except Exception as e:
            logger.error(f"Generation error: {e}")
            return "GENERATION_ERROR"