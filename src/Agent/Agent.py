# src/Agent/Agent.py

import numpy as np
from typing import Any
from src.Agent.Loop import Loop
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
        self.loop = Loop(self.config,self.Memory,self.CtxManager,self.Engine,self.TlManager)
        self.logger = get_logger("[AGENT]")
        self.steps = self.Memory.tick
        self.loop.get_tool_definitions()
        self._tool_definitions()

    def _tool_definitions(self):
        self.tool_definitions = self.TlManager.get_tools()


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

    def act(self,user_input: MemoryEvent,image: np.ndarray = None):
        response = self.loop.Process(user_input,image)
        return response

