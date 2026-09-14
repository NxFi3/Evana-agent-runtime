#src/Agent/Loop.py

from typing import Any
import numpy as np
from src.Tools.ToolManager import ToolManager
from src.Memory.MemoryManager import MemoryManager
from src.Context.ContextManager import ContextManager
from src.Engine.llmManagment.LlmProvider import LlmProvider
from src.Memory.MemoryEvent import MemoryEvent
from src.Agent.AgentState import AgentState
from src.Utils.logger import get_logger


class Loop:
    def __init__(self, config: dict[str, Any], memory: MemoryManager, ctx: ContextManager, llm: LlmProvider, tool: ToolManager) -> None:
        self.config = config
        self.memory = memory
        self.ctx = ctx
        self.llm = llm
        self.tool = tool
        self.logger = get_logger("[LOOP]")
        self.tool_definitions = []
        self.state = None
        self.failed_tool_calls = set()

    def get_tool_definitions(self):
        if not self.tool_definitions:
            self.tool_definitions = self.tool.get_tools()
        return self.tool_definitions

    def _create_event(self, event_type: str, content: str, source: str, metadata: dict[str, object] | None = None) -> MemoryEvent:
        return MemoryEvent(
            event_type=event_type,
            content=content,
            source=source,
            step=self.memory.tick + 1,
            metadata=metadata or {}
        )

    def _tool_signature(self, call):
        function = call.get("function", {})
        name = function.get("name", "")
        arguments = function.get("arguments", {})
        return name, str(arguments)

    def _execute_tools(self, tool_calls: list[Any]):
        execution = self.tool.execute(tool_calls)
        calls = execution.get("calls", [])
        results = execution.get("results", [])

        for call, result in zip(calls, results):
            function = call.get("function", {})
            tool_name = function.get("name", "")
            arguments = function.get("arguments", {})

            self.state.last_action = f"{tool_name}({arguments})"
            self.state.history["tool_calls"].append({
                "tool": tool_name,
                "arguments": arguments
            })

            self.memory.step(
                self._create_event(
                    "tool_call",
                    f"{tool_name}({arguments})",
                    "llm",
                    {
                        "tool_call": call,
                        "tool_name": tool_name,
                        "arguments": arguments
                    }
                )
            )

            content = getattr(result, "content", str(result))
            metadata = getattr(result, "metadata", {}) or {}
            metadata = {
                **metadata,
                "tool_call": call,
                "tool_name": tool_name,
                "arguments": arguments
            }

            self.state.last_observation = content

            if not getattr(result, "success", True):
                self.failed_tool_calls.add(
                    self._tool_signature(call)
                )

                self.state.history["failures"].append({
                    "tool": tool_name,
                    "arguments": arguments,
                    "result": content
                })

            self.memory.step(
                self._create_event(
                    "tool_result",
                    content,
                    "tool",
                    metadata
                )
            )

        return execution

    def Process(self, user_input: MemoryEvent, working_space: str, image: np.ndarray = None):
        self.state = AgentState(task=user_input.content)
        self.state.phase = "executing"
        self.state.iteration = 0
        self.state.progress = 0.0
        self.state.completion = False
        self.state.workspace_root = working_space
        self.ctx.set_workspace(self.state.workspace_root)
        self.failed_tool_calls.clear()

        if not self.memory.step(user_input):
            self.logger.error("Failed to store user input in memory.")
            self.state.phase = "failed"
            return ""

        context = self.ctx.build_agent_context(
            PreviousResponse={},
            User_input=user_input.content,
            STM_Result=self.memory.get_previous_events(100)
        )

        max_iterations = max(
            1,
            int(self.config.get("max_agent_iterations", 20))
        )

        response = ""

        for iteration in range(1, max_iterations + 1):
            self.state.iteration = iteration

            self.logger.info(
                f"Agent iteration {iteration}/{max_iterations}"
            )

            try:
                results = self.llm.generate(
                    context,
                    self.get_tool_definitions(),
                    image
                )
            except Exception as e:
                self.logger.error(f"LLM generation failed: {e}")
                self.state.phase = "failed"
                return response

            if not results:
                self.logger.error("LLM returned an empty response.")
                self.state.phase = "failed"
                return response

            response = results.get("response", "")
            message = results.get("message") or {}
            tool_calls = message.get("tool_calls") or []

            self.logger.info(
                f"LLM response received | tool_calls={len(tool_calls)}"
            )

            if not tool_calls:
                if response:
                    self.memory.step(
                        self._create_event(
                            "agent_action",
                            response,
                            "llm",
                            {"thinking": results.get("thinking")}
                        )
                    )

                self.state.phase = "not_completed"
                self.state.completion = True
                self.state.progress = 1.0
                return response

            tool_calls_to_execute = []

            for call in tool_calls:
                signature = self._tool_signature(call)

                if signature in self.failed_tool_calls:
                    self.logger.warning(
                        f"Skipping repeated failed tool call: {signature}"
                    )

                    self.memory.step(
                        self._create_event(
                            "tool_result",
                            "This exact tool call already failed. Do not repeat it; change the arguments or choose another approach.",
                            "tool",
                            {
                                "tool_call": call,
                                "repeated_failed_call": True
                            }
                        )
                    )
                    continue

                tool_calls_to_execute.append(call)

            if not tool_calls_to_execute:
                self.logger.warning(
                    "All requested tool calls were previously failed."
                )

                self.state.phase = "failed"
                return response

            execution = self._execute_tools(tool_calls_to_execute)

            successful_tools = sum(
                1
                for result in execution.get("results", [])
                if getattr(result, "success", True)
            )

            total_tools = len(execution.get("results", []))

            if total_tools:
                self.state.progress = min(
                    0.99,
                    self.state.progress
                    + (successful_tools / total_tools) * 0.05
                )

            context = self.ctx.build_agent_context(
                PreviousResponse=results,
                User_input=user_input.content,
                STM_Result=self.memory.get_previous_events(100)
            )

        self.state.phase = "max_iterations"
        self.state.completion = False

        self.logger.warning(
            f"Maximum agent iterations reached: {max_iterations}"
        )

        return response