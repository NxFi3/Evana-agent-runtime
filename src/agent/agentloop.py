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
        self.logger = get_logger
        self.llm = llm
        self.memory = MemoryManager(self.config, self.llm)
        self.tool = ToolManager()
        self.context = ContextService(self.config, self.llm)
        self.max_iteractions = self.config.get("iteractions", 100)

    def _execute_toolCalls(self, toolcalls: LLMResult):
        toolresult = self.tool.execute(toolcalls.tool_calls)
        for call, result in zip(toolresult.get("calls"), toolresult.get("results")):
            self.memory.step(call)
            self.memory.step(result)
        self.memory.backward()

    def run(self, user_task: MemoryEvent, workspace_directory: str = "EvanaEval"):
        events = self.memory.get_previous_events(k=20)
        context = self.context.get_context(events=events, user_task=user_task)

        for iteraction in range(self.max_iteractions):
            llmresult = self.llm.generate(context)

            if llmresult.response:
                self.memory.backward()
                return llmresult
            if llmresult.thinking:
                self.memory.step(
                    MemoryEvent(
                        event_type="assistant",
                        content=llmresult.thinking,
                        source="assistant",
                        metadata={},
                    )
                )
                self.memory.backward()
            if llmresult.tool_calls:
                self._execute_toolCalls(llmresult)
