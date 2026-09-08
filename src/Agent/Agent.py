# src/Agent/Agent.py

import numpy as np
from typing import Any

from src.Context.ContextManager import ContextManager
from src.Memory.MemoryManager import MemoryManager
from src.Memory.MemoryEvent import MemoryEvent
from src.Engine.llmManagment.LlmProvider import LlmProvider
from src.Tools.ToolManager import ToolManager
from src.Utils.logger import get_logger


class Agent:

    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config
        self.Engine = LlmProvider(self.config)
        self.Memory = MemoryManager(self.config, self.Engine)
        self.CtxManager = ContextManager(self.config, self.Engine)
        self.TlManager = ToolManager()

        self.logger = get_logger("[AGENT]")
        self.steps = self.Memory.tick

        self._tool_definitions()

    def _tool_definitions(self):
        self.tool_definitions = self.TlManager.get_tools()

    def _next_event_step(self) -> int:

        events = self.Memory.get_previous_events(1)

        if not events:
            return 1

        return events[-1].step + 1

    def _create_event(
        self,
        event_type: str,
        content: str,
        source: str,
        metadata: dict[str, object] | None = None,
    ) -> MemoryEvent:
        return MemoryEvent(
            event_type=event_type,
            content=content,
            source=source,
            step=self._next_event_step(),
            metadata=metadata or {},
        )

    def act(
        self,
        user_input: MemoryEvent,
        image: np.ndarray = None,
    ):

        if not isinstance(user_input, MemoryEvent):
            raise TypeError(
                f"user_input must be MemoryEvent, got {type(user_input)}"
            )

        if not self.Memory.step(user_input):
            self.logger.error("Failed to store user input in memory.")
            return ""


        context = self.CtxManager.build_agent_context(
            PreviousResponse={},
            User_input=user_input.content,
            STM_Result=self.Memory.get_previous_events(10),
        )


        max_iterations = self.config.get("max_agent_iterations", 20)

        for _ in range(max_iterations):

            results = self.Engine.generate(
                context,
                self.tool_definitions,
                image,
            )

            if not results:
                self.logger.error("LLM returned an empty response.")
                return ""

            response = results.get("response", "")

            message = results.get("message") or {}
            tool_calls = message.get("tool_calls") or []

            if response:
                self.Memory.step(
                    self._create_event(
                        event_type="agent_action",
                        content=response,
                        source="llm",
                        metadata={
                            "thinking": results.get("thinking"),
                        },
                    )
                )

            if not tool_calls:
                return response

            execution = self.TlManager.execute(tool_calls)

            calls = execution.get("calls", [])
            tool_results = execution.get("results", [])

            for call, tool_result in zip(calls, tool_results):

                tool_call_content = (
                    f"{call['name']}("
                    f"{call['arguments']}"
                    f")"
                )

                self.Memory.step(
                    self._create_event(
                        event_type="tool_call",
                        content=tool_call_content,
                        source="llm",
                        metadata={
                            "tool_name": call["name"],
                            "arguments": call["arguments"],
                        },
                    )
                )

                self.Memory.step(
                    self._create_event(
                        event_type="tool_result",
                        content=tool_result.content,
                        source="tool",
                        metadata=tool_result.metadata,
                    )
                )

            context = self.CtxManager.build_agent_context(
                PreviousResponse=results,
                User_input=user_input.content,
                STM_Result=self.Memory.get_previous_events(100),
            )

        self.logger.warning(
            f"Maximum agent iterations reached: {max_iterations}"
        )

        return response

