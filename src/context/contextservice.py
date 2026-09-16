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

        self.context: list[dict] = []

    def get_context(
        self,
        events: list[MemoryEvent],
        user_task: dict,
        active_skills: dict | None = None,
        agent_state: dict | None = None,
        progress: dict | None = None,
    ) -> list[dict]:

        self.context = self.contextbuilder.build_context(
            events=events,
            task=user_task,
            active_skills=active_skills,
            agent_state=agent_state,
            progress=progress,
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
