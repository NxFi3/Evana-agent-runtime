import os
from typing import Any, ClassVar

from openrouter import OpenRouter

from src.utils.logger import get_logger
from src.engine.providers.ProviderBase import ProviderBase
from src.models.LLMInput import LLMInput
from src.models.LLMResult import LLMResult

logger = get_logger("[OPENROUTER]")


class OpenRouterProvider(ProviderBase):

    name = "openrouter"

    defaultModel = "openrouter/free"

    defaultConfig: ClassVar[dict] = {
        "temperature": 0.3,
        "tool_choice": "auto",
        "parallel_tool_calls": True,
    }

    def __init__(self):
        self.client: OpenRouter | None = None

    def _create_client(self) -> None:
        if self.client is not None:
            return

        api_key = os.getenv("OPENROUTER_API_KEY")

        if not api_key:
            raise RuntimeError("OPENROUTER_API_KEY environment variable is not set")

        self.client = OpenRouter(
            api_key=api_key,
        )

    @staticmethod
    def _serialize_tool_call(tool_call: Any) -> dict:
        """
        Convert OpenRouter SDK tool-call object into the OpenAI-compatible
        dictionary shape expected by the next request.
        """

        if hasattr(tool_call, "model_dump"):
            return tool_call.model_dump(exclude_none=True)

        if isinstance(tool_call, dict):
            return tool_call

        raise TypeError(f"Unsupported tool call type: {type(tool_call).__name__}")

    @staticmethod
    def _serialize_message(message: Any) -> dict:
        """
        Preserve the assistant message exactly enough for the next
        tool-result turn.

        This is important because the assistant tool-call message and
        tool_call_id must stay paired.
        """

        if hasattr(message, "model_dump"):
            return message.model_dump(exclude_none=True)

        if isinstance(message, dict):
            return message

        raise TypeError(f"Unsupported message type: {type(message).__name__}")

    def generate(self, llminput: LLMInput) -> LLMResult:

        self._create_client()

        model_name = llminput.model_name or self.defaultModel
        messages = llminput.messages or []
        tools = llminput.tools or []

        options = dict(self.defaultConfig)

        if llminput.options:
            options.update(llminput.options)

        if not tools:
            options.pop("tool_choice", None)
            options.pop("parallel_tool_calls", None)

        try:

            request_kwargs = {
                "model": model_name,
                "messages": messages,
                "stream": False,
                **options,
            }

            if tools:
                request_kwargs["tools"] = tools

            response = self.client.chat.send(**request_kwargs)

        except Exception as exc:

            logger.error("Chat generation failed: " f"{type(exc).__name__}: {exc}")

            raise RuntimeError(
                "OpenRouter generation failed: " f"{type(exc).__name__}: {exc}"
            ) from exc

        if not response.choices:
            raise RuntimeError("OpenRouter returned no choices")

        message = response.choices[0].message

        tool_calls = list(getattr(message, "tool_calls", None) or [])

        # Convert SDK objects to plain dictionaries so the rest of
        # Evana does not depend on OpenRouter SDK types.
        normalized_tool_calls = [self._serialize_tool_call(call) for call in tool_calls]

        normalized_message = self._serialize_message(message)

        usage = getattr(response, "usage", None)

        total_tokens = getattr(usage, "total_tokens", 0) if usage is not None else 0

        # OpenRouter/OpenAI-style response may expose reasoning
        # depending on the selected model.
        thinking = getattr(message, "reasoning", None)

        logger.debug(
            f"Model={model_name} "
            f"tool_calls={len(normalized_tool_calls)} "
            f"usage={total_tokens}"
        )

        return LLMResult(
            response=getattr(message, "content", None) or "",
            message=normalized_message,
            tool_calls=normalized_tool_calls,
            thinking=thinking,
            usage=total_tokens,
            raw=response,
        )
