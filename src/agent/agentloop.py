from __future__ import annotations

from src.utils.logger import get_logger
from src.memory.MemoryManager import MemoryManager
from src.context.contextservice import ContextService
from src.tools.ToolManager import ToolManager
from src.models.MemoryEvent import MemoryEvent
from src.engine.LlmProviderManager import LlmProvider
from src.models.LLMResult import LLMResult
from src.agent.agentstate import AgentState


class Loop:

    def __init__(
        self,
        config,
        llm: LlmProvider,
    ) -> None:

        self.config = config

        self.logger = get_logger("[LOOP]")

        self.llm = llm

        self.memory = MemoryManager(
            self.config,
            self.llm,
        )

        self.tool = ToolManager()

        self.context = ContextService(
            self.config,
            self.llm,
        )

        self.agent_state = AgentState()

        try:

            self.max_iterations = int(
                self.config.get(
                    "max_agent_iterations",
                    100,
                )
            )

        except (
            TypeError,
            ValueError,
        ):

            self.max_iterations = 100

        self.max_iterations = max(
            1,
            self.max_iterations,
        )

        self.tool_definitions = self.tool.get_tools()

    @staticmethod
    def _assistant_message_to_event(
        llmresult: LLMResult,
    ) -> MemoryEvent:

        return MemoryEvent(
            event_type="assistant",
            source="assistant",
            content=(llmresult.response or ""),
            metadata={
                "llm_message": (
                    llmresult.message
                    if isinstance(
                        llmresult.message,
                        dict,
                    )
                    else {}
                ),
                "thinking": (llmresult.thinking or ""),
            },
        )

    @staticmethod
    def _tool_call_to_event(
        call,
    ) -> MemoryEvent:

        return MemoryEvent(
            event_type="tool_call",
            source="agent",
            content={
                "name": getattr(
                    call,
                    "name",
                    "",
                ),
                "args": getattr(
                    call,
                    "args",
                    {},
                ),
                "action": getattr(
                    call,
                    "action",
                    "execute",
                ),
                "target": getattr(
                    call,
                    "target",
                    "",
                ),
                "valid": getattr(
                    call,
                    "valid",
                    False,
                ),
                "approved": getattr(
                    call,
                    "approved",
                    False,
                ),
            },
            metadata={},
        )

    @staticmethod
    def _tool_result_to_event(
        result,
    ) -> MemoryEvent:

        return MemoryEvent(
            event_type="tool_result",
            source="tool",
            content={
                "name": getattr(
                    result,
                    "name",
                    "",
                ),
                "success": getattr(
                    result,
                    "success",
                    False,
                ),
                "content": getattr(
                    result,
                    "content",
                    {},
                ),
                "metadata": getattr(
                    result,
                    "metadata",
                    {},
                ),
            },
            metadata={},
        )

    def _execute_tool_calls(
        self,
        llmresult: LLMResult,
        iteration: int,
    ) -> None:

        tool_calls = llmresult.tool_calls or []

        if not tool_calls:

            self.logger.info("No tool calls to execute.")

            return

        self.logger.info(f"Executing {len(tool_calls)} tool call(s)")

        tool_result = self.tool.execute(tool_calls)

        calls = tool_result.get(
            "calls",
            [],
        )

        results = tool_result.get(
            "results",
            [],
        )

        for call in calls:

            tool_name = getattr(
                call,
                "name",
                "unknown",
            )

            args = getattr(
                call,
                "args",
                {},
            )

            valid = getattr(
                call,
                "valid",
                False,
            )

            approved = getattr(
                call,
                "approved",
                False,
            )

            action = getattr(
                call,
                "action",
                "execute",
            )

            target = getattr(
                call,
                "target",
                "",
            )

            self.logger.info(
                f"Tool call → {tool_name} "
                f"| action={action} "
                f"| target={target} "
                f"| valid={valid} "
                f"| approved={approved} "
                f"| args={args}"
            )

            self.agent_state.begin(
                tool_call=call,
                iteration=iteration,
            )

            self.memory.step(self._tool_call_to_event(call))

        for result in results:

            tool_name = getattr(
                result,
                "name",
                "unknown",
            )

            success = getattr(
                result,
                "success",
                False,
            )

            self.logger.info(f"Tool result ← {tool_name} " f"| success={success}")

            self.agent_state.update_from_result(result)

            self.memory.step(self._tool_result_to_event(result))

    def run(
        self,
        user_task: MemoryEvent,
        workspace_directory: str = "EvanaEval",
    ):

        if not isinstance(
            user_task,
            MemoryEvent,
        ):

            self.logger.error("user_task must be a MemoryEvent.")

            return None

        # New run = fresh execution state.
        self.agent_state.reset()

        self.logger.info(
            "Starting agent loop | "
            f"max_iterations="
            f"{self.max_iterations} | "
            f"workspace="
            f"{workspace_directory}"
        )

        # Persist current user task exactly once.
        existing_events = self.memory.get_previous_events(k=20)

        if not self._contains_event(
            existing_events,
            user_task,
        ):

            if not self.memory.step(user_task):

                self.logger.error("Failed to store user task.")

                return None

        for iteration in range(self.max_iterations):

            iteration_number = iteration + 1

            self.agent_state.iteration = iteration_number

            self.logger.info(f"Iteration {iteration_number}/" f"{self.max_iterations}")

            events = self.memory.get_previous_events(k=20)

            context = self.context.get_context(
                events=events,
                user_task=user_task,
                agent_state=self.agent_state,
                workspace_directory=workspace_directory,
            )

            try:

                llmresult = self.llm.generate(
                    context,
                    tools=(self.tool_definitions),
                )

            except Exception as e:

                self.logger.error(f"LLM generation failed: {e}")

                self.agent_state.fail(str(e))

                self.memory.saveall()

                return None

            if llmresult is None:

                self.logger.error("LLM returned None.")

                self.agent_state.fail("LLM returned None.")

                self.memory.saveall()

                return None

            self.context.calibrate(llmresult)

            if llmresult.tool_calls:

                self.memory.step(self._assistant_message_to_event(llmresult))

                self._execute_tool_calls(
                    llmresult,
                    iteration=iteration_number,
                )

                continue

            if llmresult.response:

                self.memory.step(self._assistant_message_to_event(llmresult))

                self.agent_state.complete()

                self.memory.saveall()

                return llmresult

            self.logger.warning("LLM produced neither " "response nor tool calls.")

        self.logger.warning("Maximum iterations reached.")

        self.agent_state.stop("Maximum iterations reached.")

        self.memory.saveall()

        return None

    @staticmethod
    def _contains_event(
        events: list[MemoryEvent],
        target: MemoryEvent,
    ) -> bool:

        target_id = getattr(
            target,
            "id",
            None,
        )

        if target_id is None:
            return False

        for event in events:

            if (
                getattr(
                    event,
                    "id",
                    None,
                )
                == target_id
            ):

                return True

        return False
