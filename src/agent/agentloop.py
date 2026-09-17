from src.utils.logger import get_logger
from src.memory.MemoryManager import MemoryManager
from src.context.contextservice import ContextService
from src.tools.ToolManager import ToolManager
from src.models.MemoryEvent import MemoryEvent
from src.engine.LlmProviderManager import LlmProvider
from src.models.LLMResult import LLMResult


class Loop:

    def __init__(self, config, llm: LlmProvider) -> None:
        self.config = config
        self.logger = get_logger("[LOOP]")

        self.llm = llm
        self.memory = MemoryManager(self.config, self.llm)
        self.tool = ToolManager()
        self.context = ContextService(self.config, self.llm)

        self.max_iterations = self.config.get(
            "iterations",
            100,
        )

    @staticmethod
    def _tool_call_to_event(call) -> MemoryEvent:
        return MemoryEvent(
            event_type="tool_call",
            source="agent",
            content={
                "name": call.name,
                "args": call.args,
                "valid": call.valid,
                "approved": call.approved,
            },
            metadata={},
        )

    @staticmethod
    def _tool_result_to_event(result) -> MemoryEvent:
        return MemoryEvent(
            event_type="tool_result",
            source="tool",
            content={
                "name": result.name,
                "success": result.success,
                "content": result.content,
                "metadata": result.metadata,
            },
            metadata={},
        )

    def _execute_tool_calls(self, llmresult: LLMResult) -> None:

        tool_result = self.tool.execute(llmresult.tool_calls)

        calls = tool_result.get("calls", [])
        results = tool_result.get("results", [])

        for call in calls:
            self.memory.step(self._tool_call_to_event(call))

        for result in results:
            self.memory.step(self._tool_result_to_event(result))

    def run(
        self,
        user_task: MemoryEvent,
        workspace_directory: str = "EvanaEval",
    ):

        for iteration in range(self.max_iterations):

            self.logger.info(f"Iteration {iteration + 1}/{self.max_iterations}")

            events = self.memory.get_previous_events(k=20)

            context = self.context.get_context(
                events=events,
                user_task=user_task,
            )

            llmresult = self.llm.generate(context)

            if llmresult is None:
                self.logger.error("LLM returned None.")
                return None

            self.context.calibrate(llmresult)

            if llmresult.tool_calls:

                if llmresult.thinking:
                    self.memory.step(
                        MemoryEvent(
                            event_type="assistant",
                            source="assistant",
                            content=llmresult.thinking,
                            metadata={},
                        )
                    )

                self._execute_tool_calls(llmresult)

                continue

            if llmresult.response:

                self.memory.step(
                    MemoryEvent(
                        event_type="assistant",
                        source="assistant",
                        content=llmresult.response,
                        metadata={},
                    )
                )

                return llmresult

            self.logger.warning("LLM produced neither response nor tool calls.")

        self.logger.warning("Maximum iterations reached.")

        return None
