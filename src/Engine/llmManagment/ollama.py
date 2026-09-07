#src/Engine/llmManagment/ollama.py

import ollama
from src.Utils.logger import get_logger
import numpy as np

logger = get_logger("[Ollama]")


class OllamaProvider:

    def __init__(self, config: dict) -> None:
        self.default_model = "gpt-oss:20b"
        self.config = config

        self.model_name = config.get("model_name") or self.default_model
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

            logger.warning(
                f"Context length not found for model: {self.model_name}"
            )
            return None

        except Exception as e:
            logger.error(f"Error fetching model context length: {e}")
            return None

    def chat(self, text: str, tools: list = None,image: np.ndarray = None):
        message = {'role':'system','content':text}
        if image is not None:
            message['images'] = [image]
        try:
            logger.info("Generating chat response")

            chat_response = ollama.chat(
                model=self.model_name,
                messages=[message],
                tools=tools,
                options=self.options,
            )

            response = chat_response.model_dump()

            # Make the output compatible with the old GenerateResponse shape.
            response["response"] = (
                chat_response.message.content
                if chat_response.message is not None
                else ""
            )

            response["thinking"] = (
                chat_response.message.thinking
                if chat_response.message is not None
                else None
            )

            # GenerateResponse compatibility fields.
            response.setdefault("context", None)
            response.setdefault("image", None)
            response.setdefault("completed", None)
            response.setdefault("total", None)

            # Keep the complete native Ollama ChatResponse.
            response["chat_response"] = chat_response

            return response

        except Exception as e:
            logger.error(f"Chat error: {e}")
            return {}
