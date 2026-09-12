#src/Agent/Loop.py

from typing import Any
import json
import numpy as np

from src.Agent.AgentState import AgentState
from src.Tools.ToolManager import ToolManager
from src.Memory.MemoryManager import MemoryManager
from src.Context.ContextManager import ContextManager
from src.Engine.llmManagment.LlmProvider import LlmProvider
from src.Memory.MemoryEvent import MemoryEvent
from src.Utils.logger import get_logger

class Loop:

    def __init__(
        self,
        config: dict[str, Any],
        memory: MemoryManager,
        ctx: ContextManager,
        llm: LlmProvider,
        tool: ToolManager,
    ) -> None:
        self.config = config
        self.memory = memory
        self.ctx = ctx
        self.llm = llm
        self.steps = self.memory.tick
        self.tool = tool
        self.logger = get_logger("[LOOP]")

        self.state = AgentState(
            task=""
        )

        self.tool_definitions = []

    def get_tool_definitions(self):
        self.tool_definitions = self.tool.get_tools()
        return self.tool_definitions

    def _create_event(
        self,
        event_type: str,
        content: str,
        source: str,
        metadata: dict[str, object] | None = None,
    ) -> MemoryEvent:
        self.steps += 1

        return MemoryEvent(
            event_type=event_type,
            content=content,
            source=source,
            step=self.steps,
            metadata=metadata or {},
        )
    def _reset_state(self, task: str) -> None:

        self.state.task = task
        self.state.iteration = 0
        self.state.phase = "observing"

        self.state.last_action = None
        self.state.last_observation = None

        self.state.progress = 0.0
        self.state.completion = False

        self.state.history["tool_calls"].clear()
        self.state.history["failures"].clear()


    def _tool_signature(self, call: dict[str, Any]) -> str:


        name = call.get("name", "")
        arguments = call.get("arguments", {})

        try:
            normalized_arguments = json.dumps(
                arguments,
                sort_keys=True,
                default=str,
                ensure_ascii=False,
            )
        except Exception:
            normalized_arguments = str(arguments)

        return f"{name}:{normalized_arguments}"

    def _record_failure(
        self,
        reason: str,
        iteration: int,
    ) -> None:


        self.state.history["failures"].append(
            {
                "iteration": iteration,
                "reason": reason,
            }
        )

        self.logger.warning(
            f"Agent loop failure at iteration {iteration}: {reason}"
        )

    def _check_repeated_tool_calls(
        self,
        calls: list[dict[str, Any]],
    ) -> bool:

        max_repetitions = self.config.get(
            "max_repeated_tool_calls",
            3,
        )

        tool_history = self.state.history["tool_calls"]

        for call in calls:
            signature = self._tool_signature(call)

            repetitions = sum(
                1
                for previous in tool_history
                if previous == signature
            )

            if repetitions >= max_repetitions:
                self._record_failure(
                    reason=(
                        f"Repeated tool call detected: "
                        f"{signature} "
                        f"(repeated {repetitions + 1} times)"
                    ),
                    iteration=self.state.iteration,
                )

                return True

        return False

    def _execute_tools(
        self,
        tool_calls: list[dict[str, Any]],
    ) -> dict[str, Any]:

        execution = self.tool.execute(tool_calls)

        calls = execution.get("calls", [])
        tool_results = execution.get("results", [])

        for call, tool_result in zip(calls, tool_results):

            tool_call_content = (
                f"{call.get('name', '')}("
                f"{call.get('arguments', {})}"
                f")"
            )

            self.state.last_action = tool_call_content

            self.memory.step(
                self._create_event(
                    event_type="tool_call",
                    content=tool_call_content,
                    source="llm",
                    metadata={
                        "tool_name": call.get("name"),
                        "arguments": call.get("arguments", {}),
                    },
                )
            )


            tool_result_content = getattr(
                tool_result,
                "content",
                str(tool_result),
            )

            self.state.last_observation = tool_result_content

            self.memory.step(
                self._create_event(
                    event_type="tool_result",
                    content=tool_result_content,
                    source="tool",
                    metadata=getattr(
                        tool_result,
                        "metadata",
                        {},
                    ),
                )
            )

        return execution

    def Process(self,user_input,image: np.ndarray = None,):

        self._reset_state(
            task=user_input.content
        )

        if not self.memory.step(user_input):
            self.logger.error(
                "Failed to store user input in memory."
            )

            self.state.phase = "failed"
            self.state.completion = False

            self._record_failure(
                reason="Failed to store user input in memory.",
                iteration=0,
            )

            return ""

        context = self.ctx.build_agent_context(
            PreviousResponse={},
            User_input=user_input.content,
            STM_Result=self.memory.get_previous_events(100),
        )

        max_iterations = int(
            self.config.get(
                "max_agent_iterations",
                20,
            )
        )

        if max_iterations <= 0:
            max_iterations = 1

        response = ""

        self.logger.info(
            f"Starting agent loop | "
            f"max_iterations={max_iterations}"
        )
        for iteration in range(1, max_iterations + 1):

            self.state.iteration = iteration
            self.state.phase = "thinking"

            self.logger.info(f"Agent iteration {iteration}/{max_iterations}")

            results = self.llm.generate(context,self.tool_definitions,image)

            if not results:

                self.logger.error("LLM returned an empty response.")

                self._record_failure(reason="LLM returned an empty response.",iteration=iteration,)
                self.state.phase = "failed"
                self.state.completion = False
                return response
            response = results.get("response","")

            message = results.get("message") or {}

            tool_calls = message.get("tool_calls") or []
            if self._check_repeated_tool_calls(tool_calls):
                self.logger.info(f"Raw tool calls: {tool_calls!r}")
            if response:
                self.state.last_observation = response
                self.memory.step(
                    self._create_event(
                        event_type="agent_action",
                        content=response,
                        source="llm",
                        metadata={
                            "thinking": results.get(
                                "thinking"
                            ),
                        },
                    )
                )
            if not tool_calls:

                self.state.phase = "completed"
                self.state.completion = True
                self.state.progress = 1.0

                self.logger.info(f"Agent completed at iteration {iteration}")
                return response
            if self._check_repeated_tool_calls(tool_calls):
                self.state.phase = "failed"
                self.state.completion = False

                self.logger.warning("Agent stopped because of repeated tool calls.")
                return response
            for call in tool_calls:
                signature = self._tool_signature(call)
                self.state.history["tool_calls"].append(signature)
            self.state.phase = "executing"
            execution = self._execute_tools(tool_calls)
            results_list = execution.get("results",[],)
            failed_tools = []
            for tool_result in results_list:
                success = getattr(tool_result,"success",True,)
                if not success:
                    failed_tools.append(
                        getattr(
                            tool_result,
                            "content",
                            "Unknown tool failure",
                        )
                    )

            if failed_tools:

                self._record_failure(
                    reason=(
                        "Tool execution failure: "
                        + " | ".join(
                            str(error)
                            for error in failed_tools
                        )
                    ),
                    iteration=iteration,
                )
            self.state.phase = "observing"

            context = self.ctx.build_agent_context(
                PreviousResponse=results,
                User_input=user_input.content,
                STM_Result=self.memory.get_previous_events(100),)
        self.logger.warning(
            f"Maximum agent iterations reached: "
            f"{max_iterations}"
        )

        self._record_failure(
            reason=(
                f"Maximum agent iterations reached: "
                f"{max_iterations}"
            ),iteration=max_iterations)

        self.state.phase = "failed"
        self.state.completion = False
        self.state.progress = 0.0

        return response

