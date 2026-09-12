#src/Agent/Loop.py

from typing import Any
from src.Tools.ToolManager import ToolManager
from src.Memory.MemoryManager import MemoryManager 
from src.Context.ContextManager import ContextManager
from src.Engine.llmManagment.LlmProvider import LlmProvider
from src.Memory.MemoryEvent import MemoryEvent
from src.Utils.logger import get_logger
import numpy as np 

class Loop:
        def __init__(self,config:dict[str,Any],memory:MemoryManager,ctx:ContextManager,llm:LlmProvider,tool:ToolManager) -> None:
            self.config = config
            self.memory = memory 
            self. ctx = ctx
            self.llm = llm
            self.tool = tool
            self.logger = get_logger('[LOOP]')
        def get_tool_definitions(self):
            self.tool_definitions =  self.tool.get_tools()



        def _create_event(
                self,
                event_type: str,
                content: str,
                source: str,
                metadata: dict[str, object] | None = None,
            ) -> MemoryEvent:
                self.steps +=1 
                return MemoryEvent(
                    event_type=event_type,
                    content=content,
                    source=source,
                    step=self.steps,
                    metadata=metadata or {},
                )
        def Process(self,user_input,image:np.ndarray=None):
            if not self.memory.step(user_input):
                self.logger.error("Failed to store user input in memory.")
                return ""


            context = self.ctx.build_agent_context(
                PreviousResponse={},
                User_input=user_input.content,
                STM_Result=self.memory.get_previous_events(100),
            )


            max_iterations = self.config.get("max_agent_iterations", 20)

            for _ in range(max_iterations):

                results = self.llm.generate(
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
                    self.memory.step(
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

                execution = self.tool.execute(tool_calls)

                calls = execution.get("calls", [])
                tool_results = execution.get("results", [])

                for call, tool_result in zip(calls, tool_results):

                    tool_call_content = (
                        f"{call['name']}("
                        f"{call['arguments']}"
                        f")"
                    )

                    self.memory.step(
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

                    self.memory.step(
                        self._create_event(
                            event_type="tool_result",
                            content=tool_result.content,
                            source="tool",
                            metadata=tool_result.metadata,
                        )
                    )

                context = self.ctx.build_agent_context(
                    PreviousResponse=results,
                    User_input=user_input.content,
                    STM_Result=self.memory.get_previous_events(100),
                )

            self.logger.warning(
                f"Maximum agent iterations reached: {max_iterations}"
            )

            return response