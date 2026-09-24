from typing import ClassVar

import ollama

from src.utils.logger import get_logger
from src.engine.providers.ProviderBase import ProviderBase
from src.models.LLMResult import LLMResult
from src.models.LLMInput import LLMInput

logger = get_logger("[OLLAMA]")


class OllamaProvider(ProviderBase):

    name = "ollama"

    defaultModel = "gpt-oss:20b"

    defaultConfig: ClassVar[dict] = {
        "temperature": 0.3,
        "num_ctx": 120000,
    }

    def generate(
        self,
        inputs: LLMInput,
    ) -> LLMResult:

        model_name = inputs.model_name or self.defaultModel

        messages = inputs.messages

        tools = inputs.tools or []

        options = dict(self.defaultConfig)

        if inputs.options:
            options.update(inputs.options)

        try:

            chat_response = ollama.chat(
                model=model_name,
                messages=messages,
                tools=tools,
                options=options,
            )

        except Exception as exc:

            logger.error("Chat generation failed: " f"{type(exc).__name__}: {exc}")

            raise RuntimeError(
                "Ollama generation failed: " f"{type(exc).__name__}: {exc}"
            ) from exc

        message = chat_response.message if chat_response else None

        prompt_tokens = (
            getattr(
                chat_response,
                "prompt_eval_count",
                0,
            )
            or 0
        )

        completion_tokens = (
            getattr(
                chat_response,
                "eval_count",
                0,
            )
            or 0
        )

        total_tokens = prompt_tokens + completion_tokens

        tool_calls = []

        if message:

            raw_tool_calls = (
                getattr(
                    message,
                    "tool_calls",
                    None,
                )
                or []
            )

            tool_calls = list(raw_tool_calls)

        return LLMResult(
            response=(message.content if message else ""),
            message=(message.model_dump() if message else {}),
            tool_calls=tool_calls,
            thinking=(
                getattr(
                    message,
                    "thinking",
                    None,
                )
                if message
                else None
            ),
            usage=total_tokens,
            raw=chat_response,
        )
