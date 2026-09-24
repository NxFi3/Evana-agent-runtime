from __future__ import annotations

from typing import Any

from src.agent.agentstate import AgentState
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
    def _task_to_dict(
        event: MemoryEvent | None,
    ) -> dict[str, Any]:

        if event is None:
            return {}

        return {
            "content": getattr(
                event,
                "content",
                "",
            ),
            "id": getattr(
                event,
                "id",
                None,
            ),
        }

    def get_context(
        self,
        events: list[MemoryEvent],
        user_task: MemoryEvent,
        agent_state: AgentState,
        working_set: dict[str, Any] | None = None,
        observation: dict[str, Any] | None = None,
        recent_actions: dict[str, Any] | None = None,
        workspace_directory: str | None = None,
    ) -> list[dict[str, Any]]:

        self.context = self.contextbuilder.build_context(
            events=events,
            task=self._task_to_dict(user_task),
            agent_state=(agent_state.state_context()),
            progress=(agent_state.progress_context()),
            working_set=working_set or {},
            observation=observation or {},
            recent_actions=recent_actions or {},
            workspace=workspace_directory,
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
