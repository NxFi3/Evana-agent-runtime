from src.Utils.logger import get_logger
from src.Engine.LlmProviderManager import LlmProvider
from src.Context.CompactorPrompt import BuildCompactorPrompt


class Compactor:

    def __init__(
        self,
        llm_provider: LlmProvider
    ):
        self.llm_provider = llm_provider
        self.logger = get_logger("[COMPACTOR]")

    def compact(
        self,
        context: str,
        max_length: int
    ) -> str:

        if not context or not context.strip():
            return ""

        try:

            prompt = BuildCompactorPrompt(
                context,
                max_length
            )

            result = self.llm_provider.generate(
                messages=[
                    {
                        "role": "system",
                        "content": prompt
                    }
                ]
            )

            if result is None:
                return ""

            compacted = str(
                result.response or ""
            ).strip()

            if not compacted:
                self.logger.error(
                    "Compactor returned empty response."
                )
                return ""

            return compacted

        except Exception as e:

            self.logger.error(
                f"Compaction error: {e}"
            )

            return ""