from typing import Any

from src.context.contextbuilder import ContextBuilder
from src.engine.LlmProviderManager import LlmProvider
from src.models.LLMResult import LLMResult
from src.models.MemoryEvent import MemoryEvent


class ContextService:

    def __init__(
        self,
        config,
        llm: LlmProvider,
    ) -> None:

        self.config = config
        self.llm = llm

        self.contextbuilder = ContextBuilder(
            self.config,
            self.llm,
        )

        self.context: list[dict[str, Any]] = []

    @staticmethod
    def _event_to_dict(
        event: MemoryEvent | None,
    ) -> dict[str, Any]:

        if event is None:
            return {}

        return {
            "event_type": getattr(event, "event_type", ""),
            "source": getattr(event, "source", ""),
            "content": getattr(event, "content", ""),
            "step": getattr(event, "step", 0),
            "timestamp": str(getattr(event, "timestamp", "")),
        }

    def get_context(
        self,
        events: list[MemoryEvent],
        user_task: MemoryEvent,
        active_skills: MemoryEvent | None = None,
        agent_state: MemoryEvent | None = None,
        progress: MemoryEvent | None = None,
    ) -> list[dict[str, Any]]:

        self.context = self.contextbuilder.build_context(
            events=events,
            task=self._event_to_dict(user_task),
            active_skills=self._event_to_dict(active_skills),
            agent_state=self._event_to_dict(agent_state),
            progress=self._event_to_dict(progress),
        )

        return self.context

    def calibrate(
        self,
        llmresult: LLMResult,
    ) -> None:

        self.contextbuilder.tokenbudget.calibrate_from_response(
            self.context,
            llmresult,
        )
