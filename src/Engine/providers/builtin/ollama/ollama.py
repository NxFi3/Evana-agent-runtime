# src/Engine/providers/builtin/ollama/ollama.py

from typing import ClassVar
import ollama
from src.Utils.logger import get_logger
from src.Engine.providers.ProviderBase import ProviderBase
from src.Engine.providers.LLMResult import LLMResult
from src.Engine.providers.LLMInput import LLMInput

logger = get_logger("[OLLAMA]")


class OllamaProvider(ProviderBase):
    name = "ollama"
    defaultModel = "gpt-oss:20b"
    defaultConfig: ClassVar[dict] = {"temperature": 0.3,'num_ctx':120000}

    def generate(self, inputs: LLMInput) -> LLMResult:
        model_name = inputs.model_name or self.defaultModel
        messages = inputs.messages
        tools = inputs.tools or []
        options = inputs.options or dict(self.defaultConfig)

        try:
            chat_response = ollama.chat(
                model=model_name,
                messages=messages,
                tools=tools,
                options=options,
            )
        except Exception as e:
            logger.error(f"Chat error: {e}")
            raise
           

        message = chat_response.message
        prompt_tokens = getattr(chat_response, "prompt_eval_count", 0) or 0
        completion_tokens = getattr(chat_response, "eval_count", 0) or 0
        total_tokens = prompt_tokens + completion_tokens

        return LLMResult(
            response=message.content if message else "",
            message=message.model_dump() if message else {},
            tool_calls=list(message.tool_calls) if message and message.tool_calls else [],
            thinking=getattr(message, "thinking", None) if message else None,
            usage=total_tokens,
            raw=chat_response,
        )