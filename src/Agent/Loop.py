import json
import os
from typing import Any

import numpy as np

from src.Agent.AgentState import AgentState
from src.Agent.CompletionEvaluator import CompletionEvaluator
from src.Context.ContextManager import ContextManager
from src.Engine.LlmProviderManager import LlmProvider
from src.Engine.providers.LLMResult import LLMResult
from src.Memory.MemoryEvent import MemoryEvent
from src.Memory.MemoryManager import MemoryManager
from src.Tools.ToolManager import ToolManager
from src.Utils.logger import get_logger


class Loop:
    def __init__(
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

        self.logger = get_logger("[LOOP]")

        self.state: AgentState | None = None
        self.tool_definitions: list[dict] | None = None

        self.tool_failure_counts: dict[tuple[str, str], int] = {}
        self.max_same_tool_failures = 3

        self.completion_evaluator = CompletionEvaluator(self.llm)

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
        """
        Extract tool name and raw arguments from a tool call.

        Raw arguments are intentionally preserved here because the
        actual ToolManager may expect them in their original format.
        """

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

    def _parse_tool_arguments(
        self,
        arguments: Any,
    ) -> dict:
        """
        Normalize tool arguments into a dictionary for history,
        signatures, and internal bookkeeping.

        Providers may return arguments as either:
        - dict
        - JSON string
        - None
        """

        if isinstance(arguments, dict):
            return arguments

        if arguments is None:
            return {}

        if isinstance(arguments, str):
            arguments = arguments.strip()

            if not arguments:
                return {}

            try:
                parsed = json.loads(arguments)

            except (json.JSONDecodeError, TypeError):
                return {}

            if isinstance(parsed, dict):
                return parsed

            return {}

        return {}

    def _compact_tool_call_for_history(
        self,
        tool_call: Any,
    ) -> dict:
        """
        Preserve only small, task-relevant tool arguments.

        Large payloads such as file contents are intentionally
        excluded from history. The goal is to preserve enough
        information for the model to understand what action was
        performed without duplicating large inputs.
        """

        name, arguments = self._get_tool_call_data(tool_call)

        name = str(name).strip()

        arguments = self._parse_tool_arguments(arguments)

        call_id = getattr(
            tool_call,
            "id",
            None,
        )

        call_type = getattr(
            tool_call,
            "type",
            "function",
        )

        if isinstance(tool_call, dict):
            call_id = tool_call.get(
                "id",
                call_id,
            )

            call_type = tool_call.get(
                "type",
                call_type,
            )

        compact_arguments: dict[str, Any] = {}

        normalized_name = name.lower()

        if normalized_name in {
            "read",
            "readfile",
        }:
            for key in (
                "file_path",
                "start_line",
                "end_line",
            ):
                if key in arguments:
                    compact_arguments[key] = arguments[key]

        elif normalized_name in {
            "create",
            "createfile",
            "edit",
            "editfile",
        }:
            if "file_path" in arguments:
                compact_arguments["file_path"] = arguments["file_path"]

        elif normalized_name == "shell":
            for key in (
                "command",
                "cwd",
                "background",
                "timeout",
            ):
                if key in arguments:
                    compact_arguments[key] = arguments[key]

        else:
            # Unknown tools should still retain their small arguments.
            # Large string values are excluded.
            for key, value in arguments.items():

                if isinstance(value, str) and len(value) > 1000:
                    continue

                compact_arguments[key] = value

        return {
            "id": call_id,
            "type": call_type,
            "function": {
                "name": name,
                "arguments": compact_arguments,
            },
        }

    def _tool_signature(
        self,
        tool_call: Any,
    ) -> tuple[str, str]:
        """
        Build a stable signature for repeated-failure detection.

        JSON arguments are normalized so equivalent dictionaries
        produce the same signature regardless of key ordering.
        """

        name, arguments = self._get_tool_call_data(tool_call)

        name = str(name).strip().lower()

        normalized_arguments = self._parse_tool_arguments(arguments)

        try:
            serialized_arguments = json.dumps(
                normalized_arguments,
                sort_keys=True,
                ensure_ascii=False,
                separators=(
                    ",",
                    ":",
                ),
            )

        except (TypeError, ValueError):
            serialized_arguments = str(
                normalized_arguments,
            )

        return (
            name,
            serialized_arguments,
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
        content = str(content or "")

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

        omitted = len(content) - head - tail

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
            self.logger.warning(f"Workspace directory does not exist: {root}")

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
            self.logger.warning(f"Failed to refresh workspace files: {e}")

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
        execution = self.tools.execute(tool_calls)

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
            tool_name, arguments = self._get_tool_call_data(call)

            tool_name = str(tool_name).strip()

            self.state.last_action = f"Executed {tool_name}"

            compact_tool_call = self._compact_tool_call_for_history(call)

            self.memory.step(
                self._create_event(
                    event_type="tool_call",
                    content=tool_name,
                    source="llm",
                    metadata={
                        "tool_call": compact_tool_call,
                        "tool_name": tool_name,
                    },
                )
            )

            content = getattr(
                result,
                "content",
                str(result),
            )

            content = str(content or "")

            result_metadata = (
                getattr(
                    result,
                    "metadata",
                    {},
                )
                or {}
            )

            metadata = {
                **result_metadata,
                "tool_name": tool_name,
            }

            success = getattr(
                result,
                "success",
                True,
            )

            preview = self._preview_tool_result(content)

            if preview != content:
                metadata = {
                    **metadata,
                    "truncated": True,
                    "original_length": len(content),
                    "stored_length": len(preview),
                }

            self.state.last_observation = preview

            if not success:
                signature = self._tool_signature(call)

                failure_count = (
                    self.tool_failure_counts.get(
                        signature,
                        0,
                    )
                    + 1
                )

                self.tool_failure_counts[signature] = failure_count

                self.logger.warning(
                    f"Tool failed: "
                    f"{tool_name}"
                    f"({self._parse_tool_arguments(arguments)}) "
                    f"| failure="
                    f"{failure_count}/"
                    f"{self.max_same_tool_failures}"
                )

                metadata = {
                    **metadata,
                    "failure_count": failure_count,
                }

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
        events = self.memory.get_previous_events(100)

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

        self.tool_failure_counts.clear()

        self._refresh_workspace_files()

        self.context.set_workspace(working_space)

        if not self.memory.step(user_input):
            self.logger.error("Failed to store user input in memory.")

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

            self.logger.info(f"Agent iteration " f"{iteration}/{max_iterations}")

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
                        f"LLM generation failed " f"(attempt {attempt}/3): {e}"
                    )

                    if attempt == 3:
                        self.logger.error("LLM generation failed " "after 3 attempts.")

                        self.state.phase = "failed"

                        return final_response

            if not isinstance(
                result,
                LLMResult,
            ):
                self.logger.error("LLM provider returned " "an invalid result.")

                self.state.phase = "failed"

                return final_response

            previous_response = result

            final_response = result.response or ""

            tool_calls = result.tool_calls or []

            self.logger.info(
                f"LLM response received | " f"tool_calls={len(tool_calls)}"
            )

            if not tool_calls:

                if final_response:
                    self.state.last_action = final_response

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

                evaluation = self._evaluate_completion(
                    task=user_input.content,
                    latest_response=final_response,
                )

                self.logger.info(
                    "Completion evaluation | " f"complete={evaluation.complete}"
                )

                if evaluation.complete:
                    self.state.phase = "completed"
                    self.state.completion = True

                    self.logger.info("Agent turn completed.")

                    return final_response

                feedback = (
                    evaluation.feedback.strip()
                    or "The task is not complete. Continue working."
                )

                self.logger.warning("Completion rejected. " f"Feedback: {feedback}")

                self.memory.step(
                    self._create_event(
                        event_type="tool_result",
                        content=("Completion evaluator feedback:\n" + feedback),
                        source="system",
                        metadata={
                            "completion_evaluator": True,
                            "complete": False,
                        },
                    )
                )

                continue

            executable_calls = []

            for call in tool_calls:
                signature = self._tool_signature(call)

                failure_count = self.tool_failure_counts.get(
                    signature,
                    0,
                )

                if failure_count >= self.max_same_tool_failures:
                    tool_name, _ = self._get_tool_call_data(call)

                    tool_name = str(tool_name).strip()

                    self.logger.warning(
                        "Blocking repeatedly failed " f"tool call: {tool_name}"
                    )

                    self.memory.step(
                        self._create_event(
                            event_type="tool_result",
                            content=(
                                "This exact tool call has "
                                f"failed {failure_count} times. "
                                "Do not repeat it. "
                                "Change the arguments or "
                                "use a different approach."
                            ),
                            source="system",
                            metadata={
                                "tool_name": tool_name,
                                "repeated_failed_call": True,
                                "failure_count": failure_count,
                            },
                        )
                    )

                    continue

                executable_calls.append(call)

            if not executable_calls:
                self.logger.warning(
                    "All requested tool calls are " "currently blocked."
                )

                self.memory.step(
                    self._create_event(
                        event_type="tool_result",
                        content=(
                            "The requested tool calls have "
                            "failed repeatedly. "
                            "You must change your approach."
                        ),
                        source="system",
                        metadata={
                            "recovery_required": True,
                        },
                    )
                )

                continue

            try:
                self._execute_tools(executable_calls)

            except Exception as e:
                self.logger.error(f"Tool execution failed: {e}")

                self.state.phase = "failed"
                self.state.completion = False

                return final_response

        self.state.phase = "max_iterations"
        self.state.completion = False

        self.logger.warning(f"Maximum agent iterations reached: " f"{max_iterations}")

        return final_response
