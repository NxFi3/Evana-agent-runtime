from typing import Any
import os
import numpy as np

from src.Agent.AgentState import AgentState
from src.Agent.CompletionEvaluator import CompletionEvaluator
from src.Context.ContextManager import ContextManager
from src.Memory.MemoryEvent import MemoryEvent
from src.Memory.MemoryManager import MemoryManager
from src.Tools.ToolManager import ToolManager
from src.Utils.logger import get_logger

from src.Engine.LlmProviderManager import LlmProvider
from src.Engine.providers.LLMResult import LLMResult

class Loop:
def **init**(
self,
config: dict,
memory: MemoryManager,
context: ContextManager,
llm: LlmProvider,
tools: ToolManager,
):
self.config = config
self.memory = memory
self.context = context
self.llm = llm
self.tools = tools

```
    self.logger = get_logger("[LOOP]")

    self.state: AgentState | None = None
    self.tool_definitions: list[dict] | None = None
    self.failed_tool_calls: set[tuple[str, str]] = set()

    self.completion_evaluator = CompletionEvaluator(
        self.llm
    )

    context_config = self.config.get("context") or {}

    self.tool_result_max_chars = int(
        context_config.get(
            "tool_result_max_chars",
            6000,
        )
    )

    self.tool_result_preview_head = int(
        context_config.get(
            "tool_result_preview_head",
            4500,
        )
    )

    self.tool_result_preview_tail = int(
        context_config.get(
            "tool_result_preview_tail",
            1000,
        )
    )

def _get_tool_definitions(self) -> list[dict]:
    if self.tool_definitions is None:
        self.tool_definitions = self.tools.get_tools()

    return self.tool_definitions

def _get_tool_call_data(
    self,
    tool_call: Any,
) -> tuple[str, Any]:

    if hasattr(tool_call, "function"):
        function = tool_call.function

        name = getattr(
            function,
            "name",
            "",
        )

        arguments = getattr(
            function,
            "arguments",
            {},
        )

        return name, arguments

    if isinstance(tool_call, dict):

        function = tool_call.get(
            "function",
            {},
        )

        if not isinstance(
            function,
            dict,
        ):
            return "", {}

        name = function.get(
            "name",
            "",
        )

        arguments = function.get(
            "arguments",
            {},
        )

        return name, arguments

    return "", {}

def _tool_signature(
    self,
    tool_call: Any,
) -> tuple[str, str]:

    name, arguments = self._get_tool_call_data(
        tool_call
    )

    return (
        str(name).strip().lower(),
        str(arguments),
    )

def _create_event(
    self,
    event_type: str,
    content: str,
    source: str,
    metadata: dict | None = None,
) -> MemoryEvent:

    return MemoryEvent(
        event_type=event_type,
        content=content,
        source=source,
        step=self.memory.tick + 1,
        metadata=metadata or {},
    )

def _preview_tool_result(
    self,
    content: str,
) -> str:

    content = str(
        content or ""
    )

    max_chars = max(
        1,
        self.tool_result_max_chars,
    )

    if len(content) <= max_chars:
        return content

    head = min(
        self.tool_result_preview_head,
        len(content),
    )

    remaining = len(content) - head

    tail = min(
        self.tool_result_preview_tail,
        remaining,
    )

    if head + tail >= len(content):
        return content

    omitted = (
        len(content)
        - head
        - tail
    )

    return (
        content[:head]
        + "\n\n"
        + f"... [{omitted} characters truncated] ..."
        + "\n\n"
        + content[-tail:]
    )

def _refresh_workspace_files(
    self,
) -> None:

    if self.state is None:
        return

    root = self.state.workspace_root

    if not root:
        self.state.workspace_files = []
        return

    if not os.path.isdir(root):

        self.logger.warning(
            f"Workspace directory does not exist: {root}"
        )

        self.state.workspace_files = []
        return

    files: list[str] = []

    ignored_directories = {
        ".git",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        "node_modules",
    }

    try:

        for current_root, dirs, filenames in os.walk(root):

            dirs[:] = [
                directory
                for directory in dirs
                if directory not in ignored_directories
            ]

            for filename in filenames:

                full_path = os.path.join(
                    current_root,
                    filename,
                )

                relative_path = os.path.relpath(
                    full_path,
                    root,
                )

                files.append(
                    relative_path.replace(
                        os.sep,
                        "/",
                    )
                )

        files.sort()

        self.state.workspace_files = files

    except Exception as e:

        self.logger.warning(
            f"Failed to refresh workspace files: {e}"
        )

def _build_context(
    self,
    user_input: str,
    previous_response: LLMResult | None,
):

    self._refresh_workspace_files()

    return self.context.build_agent_context(
        previous_response=previous_response,
        user_input=user_input,
        stm_result=self.memory.get_previous_events(100),
        agent_state=self.state,
    )

def _execute_tools(
    self,
    tool_calls: list[Any],
) -> dict:

    execution = self.tools.execute(
        tool_calls
    )

    calls = execution.get(
        "calls",
        [],
    )

    results = execution.get(
        "results",
        [],
    )

    for call, result in zip(
        calls,
        results,
    ):

        tool_name, arguments = (
            self._get_tool_call_data(
                call
            )
        )

        action = (
            f"{tool_name}({arguments})"
        )

        self.state.last_action = action

        self.memory.step(
            self._create_event(
                event_type="tool_call",
                content=action,
                source="llm",
                metadata={
                    "tool_call": call,
                    "tool_name": tool_name,
                    "arguments": arguments,
                },
            )
        )

        content = getattr(
            result,
            "content",
            str(result),
        )

        content = str(
            content or ""
        )

        metadata = getattr(
            result,
            "metadata",
            {},
        ) or {}

        metadata = {
            **metadata,
            "tool_call": call,
            "tool_name": tool_name,
            "arguments": arguments,
        }

        success = getattr(
            result,
            "success",
            True,
        )

        preview = (
            self._preview_tool_result(
                content
            )
        )

        if preview != content:

            metadata = {
                **metadata,
                "truncated": True,
                "original_length": len(content),
                "stored_length": len(preview),
            }

        self.state.last_observation = (
            preview
        )

        if not success:

            signature = (
                self._tool_signature(
                    call
                )
            )

            self.failed_tool_calls.add(
                signature
            )

            self.logger.warning(
                f"Tool failed: "
                f"{tool_name}({arguments})"
            )

        self.memory.step(
            self._create_event(
                event_type="tool_result",
                content=preview,
                source="tool",
                metadata=metadata,
            )
        )

    self._refresh_workspace_files()

    return execution

def _evaluate_completion(
    self,
    task: str,
    latest_response: str,
):
    events = self.memory.get_previous_events(
        100
    )

    return self.completion_evaluator.evaluate(
        task=task,
        latest_response=latest_response,
        events=events,
    )

def run(
    self,
    user_input: MemoryEvent,
    working_space: str,
    image: np.ndarray | None = None,
) -> str:

    self.state = AgentState(
        task=user_input.content,
        workspace_root=working_space,
    )

    self.state.phase = "executing"
    self.state.iteration = 0
    self.state.completion = False

    self.failed_tool_calls.clear()

    self._refresh_workspace_files()

    self.context.set_workspace(
        working_space
    )

    if not self.memory.step(
        user_input
    ):

        self.logger.error(
            "Failed to store user input in memory."
        )

        self.state.phase = "failed"

        return ""

    previous_response: LLMResult | None = None
    final_response = ""

    max_iterations = max(
        1,
        int(
            self.config.get(
                "max_agent_iterations",
                20,
            )
        ),
    )

    for iteration in range(
        1,
        max_iterations + 1,
    ):

        self.state.iteration = iteration

        self.logger.info(
            f"Agent iteration "
            f"{iteration}/{max_iterations}"
        )

        context = self._build_context(
            user_input=user_input.content,
            previous_response=previous_response,
        )

        result: LLMResult | None = None

        for attempt in range(
            1,
            4,
        ):

            try:

                result = self.llm.generate(
                    context,
                    self._get_tool_definitions(),
                    image,
                )

                break

            except Exception as e:

                self.logger.warning(
                    f"LLM generation failed "
                    f"(attempt {attempt}/3): {e}"
                )

                if attempt == 3:

                    self.logger.error(
                        "LLM generation failed "
                        "after 3 attempts."
                    )

                    self.state.phase = "failed"

                    return final_response

        if not isinstance(
            result,
            LLMResult,
        ):

            self.logger.error(
                "LLM provider returned "
                "an invalid result."
            )

            self.state.phase = "failed"

            return final_response

        previous_response = result

        final_response = (
            result.response or ""
        )

        tool_calls = (
            result.tool_calls or []
        )

        self.logger.info(
            f"LLM response received | "
            f"tool_calls={len(tool_calls)}"
        )

        # -------------------------------------------------
        # No tool calls:
        # ask the completion judge before stopping.
        # -------------------------------------------------

        if not tool_calls:

            if final_response:

                self.state.last_action = (
                    final_response
                )

                self.memory.step(
                    self._create_event(
                        event_type="agent_action",
                        content=final_response,
                        source="llm",
                        metadata={
                            "thinking": result.thinking,
                        },
                    )
                )

            evaluation = (
                self._evaluate_completion(
                    task=user_input.content,
                    latest_response=final_response,
                )
            )

            self.logger.info(
                "Completion evaluation | "
                f"complete={evaluation.complete}"
            )

            if evaluation.complete:

                self.state.phase = "completed"
                self.state.completion = True

                self.logger.info(
                    "Agent turn completed."
                )

                return final_response

            feedback = (
                evaluation.feedback.strip()
                or (
                    "The task is not complete. "
                    "Continue working."
                )
            )

            self.logger.warning(
                "Completion rejected. "
                f"Feedback: {feedback}"
            )

            self.memory.step(
                self._create_event(
                    event_type="tool_result",
                    content=(
                        "Completion evaluator feedback:\n"
                        + feedback
                    ),
                    source="system",
                    metadata={
                        "completion_evaluator": True,
                        "complete": False,
                    },
                )
            )

            continue

        # -------------------------------------------------
        # Filter previously failed exact tool calls.
        # -------------------------------------------------

        executable_calls = []

        for call in tool_calls:

            signature = (
                self._tool_signature(
                    call
                )
            )

            if signature in self.failed_tool_calls:

                self.logger.warning(
                    "Skipping repeated failed "
                    "tool call: "
                    + str(signature)
                )

                self.memory.step(
                    self._create_event(
                        event_type="tool_result",
                        content=(
                            "This exact tool call already failed. "
                            "Do not repeat it; change the arguments "
                            "or choose another approach."
                        ),
                        source="tool",
                        metadata={
                            "tool_call": call,
                            "repeated_failed_call": True,
                        },
                    )
                )

                continue

            executable_calls.append(
                call
            )

        if not executable_calls:

            self.logger.warning(
                "All requested tool calls were "
                "previously failed."
            )

            self.state.phase = "failed"
            self.state.completion = False

            return final_response

        try:

            self._execute_tools(
                executable_calls
            )

        except Exception as e:

            self.logger.error(
                f"Tool execution failed: {e}"
            )

            self.state.phase = "failed"
            self.state.completion = False

            return final_response

    self.state.phase = "max_iterations"
    self.state.completion = False

    self.logger.warning(
        f"Maximum agent iterations reached: "
        f"{max_iterations}"
    )

    return final_response
```
