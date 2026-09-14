from typing import Any, Dict, List
from src.Utils.logger import get_logger
from src.Engine.LlmProviderManager import LlmProvider
from src.Engine.providers.LLMResult import LLMResult

logger = get_logger("[TOKENBUDGET]")


class TokenBudget:
    def __init__(
        self,
        config: Dict[str, Any],
        llm_provider: LlmProvider
    ) -> None:

        self.config = config.get("context") or {}
        self.llm_provider = llm_provider

        context_length = self.llm_provider.model.defaultConfig.get(
            "num_ctx",
            120000
        )

        self.context_length = int(context_length)

        self.safe_margin = self.config.get(
            "safe_margin",
            -1
        )

        if self.safe_margin < 0:
            self.safe_margin = int(
                self.context_length * 0.15
            )

        self.budget = (
            self.context_length
            - self.safe_margin
        )

        # Initial approximation.
        self.chars_per_token = float(
            self.config.get(
                "initial_chars_per_token",
                4.0
            )
        )

        self.calibration_alpha = float(
            self.config.get(
                "calibration_alpha",
                0.2
            )
        )

        # Prevent unstable calibration.
        self.min_chars_per_token = float(
            self.config.get(
                "min_chars_per_token",
                1.5
            )
        )

        self.max_chars_per_token = float(
            self.config.get(
                "max_chars_per_token",
                8.0
            )
        )

        logger.info(
            f"Context length={self.context_length}, "
            f"budget={self.budget}, "
            f"safe_margin={self.safe_margin}, "
            f"initial_chars_per_token={self.chars_per_token}"
        )


    def _message_character_count(
        self,
        message: Dict[str, Any]
    ) -> int:

        total = 0

        # Content.
        content = message.get("content")

        if content:
            total += len(str(content))

        # Tool calls.
        tool_calls = message.get("tool_calls")

        if tool_calls:
            total += len(str(tool_calls))

        # Other fields that may contribute to serialized context.
        for key in (
            "name",
            "tool_name",
            "tool_call_id",
        ):
            value = message.get(key)

            if value:
                total += len(str(value))

        return total


    def estimate_messages_tokens(
        self,
        messages: List[Dict[str, Any]]
    ) -> int:

        if not messages:
            return 0

        total_chars = sum(
            self._message_character_count(message)
            for message in messages
        )

        if total_chars <= 0:
            return 0

        estimated_tokens = int(
            total_chars / self.chars_per_token
        )

        return max(
            1,
            estimated_tokens
        )


    def calibrate_from_response(
        self,
        messages: List[Dict[str, Any]],
        model_response: LLMResult
    ) -> None:

        if not messages:
            return

        if model_response is None:
            return

        raw = model_response.raw

        if raw is None:
            return

        actual_prompt_tokens = getattr(
            raw,
            "prompt_eval_count",
            0
        ) or 0

        actual_prompt_tokens = int(
            actual_prompt_tokens
        )

        if actual_prompt_tokens <= 0:
            return

        measured_chars = sum(
            self._message_character_count(message)
            for message in messages
        )

        if measured_chars <= 0:
            return

        observed_chars_per_token = (
            measured_chars
            / actual_prompt_tokens
        )

        observed_chars_per_token = max(
            self.min_chars_per_token,
            min(
                self.max_chars_per_token,
                observed_chars_per_token
            )
        )

        alpha = max(
            0.01,
            min(
                1.0,
                self.calibration_alpha
            )
        )

        old_ratio = self.chars_per_token

        self.chars_per_token = (
            (1.0 - alpha) * old_ratio
            + alpha * observed_chars_per_token
        )

        logger.debug(
            "Token calibration: "
            f"chars={measured_chars}, "
            f"actual_prompt_tokens={actual_prompt_tokens}, "
            f"observed_ratio={observed_chars_per_token:.3f}, "
            f"updated_ratio={self.chars_per_token:.3f}"
        )


    def used_tokens(
        self,
        model_response: LLMResult
    ) -> int:

        if model_response is None:
            return 0

        raw = model_response.raw

        if raw is not None:
            prompt_tokens = getattr(
                raw,
                "prompt_eval_count",
                0
            ) or 0

            if prompt_tokens:
                return int(prompt_tokens)

        return int(
            model_response.usage
        )


    def remaining_budget(
        self,
        model_response: LLMResult
    ) -> int:

        return (
            self.budget
            - self.used_tokens(model_response)
        )


    def is_within_budget(
        self,
        model_response: LLMResult
    ) -> bool:

        remaining = self.remaining_budget(
            model_response
        )

        if remaining <= 0:

            logger.warning(
                f"Context budget exceeded: "
                f"used={self.used_tokens(model_response)}, "
                f"budget={self.budget}"
            )

            return False

        return True