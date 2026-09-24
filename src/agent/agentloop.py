from __future__ import annotations

import json
import re
from typing import Any

from src.agent.agentstate import AgentState
from src.context.contextservice import ContextService
from src.context.workingset import WorkingSet
from src.engine.LlmProviderManager import LlmProvider
from src.memory.MemoryManager import MemoryManager
from src.models.LLMResult import LLMResult
from src.models.MemoryEvent import MemoryEvent
from src.models.ToolResult import ToolResult
from src.tools.ToolManager import ToolManager
from src.utils.logger import get_logger


class Loop:
    """
    Autonomous agent execution loop.

    The loop repeatedly:

        1. Builds the model-visible context.
        2. Asks the LLM for the next action.
        3. Dispatches and executes tool calls.
        4. Updates runtime state (agent state, working set, memory).
        5. Detects stuck / duplicate / failed action patterns.

    The loop terminates when:

        - the model returns a final response (task complete),
        - a stuck / duplicate / failure threshold is reached,
        - the model returns nothing twice in a row,
        - or the maximum iteration budget is exhausted.

    When the loop stops without a final answer it still returns an
    LLMResult that explains why, so the caller always has something to show.

    Duplicate handling policy:

        Only EXACT duplicates are blocked: the same tool called with the
        same arguments after having already succeeded at the current
        workspace revision. This is the only notion of duplicate that is
        safe for every tool.

        Target-based duplicate detection is intentionally NOT performed:

            - ``apply_patch`` on the same file is a normal, expected
              workflow step. Every patch produces different content.
            - ``read_file`` with narrower ranges on the same file is a
              legitimate way to look at additional lines.
            - ``command_exec`` with different arguments on the same target
              is a legitimate way to run a different command.

        Blocking those cases would make the loop unwinnable.
    """

    FAILURE_STUCK_THRESHOLD = 3
    DUPLICATE_BLOCK_THRESHOLD = 4
    EMPTY_RESPONSE_THRESHOLD = 2

    DEFAULT_MAX_ITERATIONS = 100

    EVENT_HISTORY_WINDOW = 200

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
        self.working_set = WorkingSet()

        self.workspace_revision = 0

        # Exact-call duplicate detection.
        self._successful_tool_calls: dict[str, int] = {}
        self._last_duplicate_key: str | None = None
        self._duplicate_block_streak = 0

        # Failure-based stuck detection.
        self._recent_failure_signatures: list[str] = []

        self.max_iterations = self._read_max_iterations()

        self.tool_definitions = self.tool.get_tools()

    def _read_max_iterations(self) -> int:
        try:
            value = int(
                self.config.get(
                    "max_agent_iterations",
                    self.DEFAULT_MAX_ITERATIONS,
                )
            )
        except (TypeError, ValueError):
            value = self.DEFAULT_MAX_ITERATIONS

        return max(1, value)

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
                    llmresult.message if isinstance(llmresult.message, dict) else {}
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
                "name": getattr(call, "name", ""),
                "tool_call_id": getattr(call, "id", ""),
                "args": getattr(call, "args", {}),
                "action": getattr(call, "action", "execute"),
                "target": getattr(call, "target", ""),
                "valid": getattr(call, "valid", False),
                "approved": getattr(call, "approved", False),
            },
            metadata={},
        )

    @staticmethod
    def _tool_result_to_event(
        call,
        result: ToolResult,
    ) -> MemoryEvent:

        return MemoryEvent(
            event_type="tool_result",
            source="tool",
            content={
                "name": getattr(result, "name", ""),
                "tool_call_id": getattr(call, "id", ""),
                "success": getattr(result, "success", False),
                "content": getattr(result, "content", {}),
                "metadata": getattr(result, "metadata", {}),
            },
            metadata={},
        )

    @staticmethod
    def _tool_call_key(
        call,
    ) -> str:
        """
        Stable identity for an exact tool call.

        The identity is (tool name + full argument payload). Two calls
        are considered duplicates only when every argument matches.
        """

        payload = {
            "name": str(getattr(call, "name", "")).strip().lower(),
            "args": getattr(call, "args", {}) or {},
        }

        try:
            return json.dumps(
                payload,
                ensure_ascii=False,
                sort_keys=True,
                default=str,
            )
        except Exception:
            return repr(payload)

    @staticmethod
    def _failure_signature(
        call,
        result: ToolResult,
    ) -> str:
        """
        Stable signature for repeated failures.

        Normalizes numeric values and hex addresses so that errors
        that only differ in IDs or timestamps are treated as the same
        class of failure.
        """

        error_msg = ""

        content = result.content
        if isinstance(content, dict):
            error = content.get("error")
            if isinstance(error, dict):
                error_msg = str(error.get("message", ""))
            elif isinstance(error, str):
                error_msg = error

        if not error_msg:
            error_msg = result.summary or "unknown"

        error_signature = re.sub(
            r"0x[0-9a-fA-F]+",
            "0xADDR",
            error_msg,
        )
        error_signature = re.sub(
            r"\d+",
            "N",
            error_signature,
        )
        error_signature = error_signature[:150]

        tool_name = str(getattr(call, "name", "unknown")).strip()

        return f"{tool_name}::{error_signature}"

    @staticmethod
    def _duplicate_result(
        call,
        reason: str,
    ) -> ToolResult:

        tool_name = str(getattr(call, "name", "unknown")).strip()
        target = str(getattr(call, "target", "")).strip()

        target_suffix = f" on {target}" if target else ""

        summary = (
            f"DUPLICATE BLOCKED: '{tool_name}'{target_suffix}. "
            f"{reason} "
            f"The earlier result is already in the conversation above. "
            f"Do NOT repeat this exact call. Use that result, or call again "
            f"with different arguments (for example a narrower line range), "
            f"or move on to the next step of the task."
        )

        return ToolResult(
            success=False,
            name=tool_name,
            content={
                "success": False,
                "error": {
                    "type": "duplicate_action",
                    "message": summary,
                },
            },
            metadata={
                "duplicate_action": True,
            },
            summary=summary,
        )

    @staticmethod
    def _missing_result(
        call,
    ) -> ToolResult:

        tool_name = str(getattr(call, "name", "unknown")).strip()

        return ToolResult(
            success=False,
            name=tool_name,
            content={
                "success": False,
                "error": {
                    "type": "missing_tool_result",
                    "message": (
                        "ToolManager did not return a result for this tool call."
                    ),
                },
            },
            metadata={},
            summary=("Tool execution produced no result."),
        )

    @staticmethod
    def _invalid_result(
        call,
    ) -> ToolResult:

        tool_name = str(getattr(call, "name", "unknown")).strip()

        return ToolResult(
            success=False,
            name=tool_name,
            content={
                "success": False,
                "error": {
                    "type": "invalid_tool_call",
                    "message": "Invalid tool call.",
                },
            },
            metadata={},
            summary="Invalid tool call.",
        )

    def _stopped_result(
        self,
        reason: str,
        remember: bool = True,
    ) -> LLMResult:
        """
        Result returned when the loop stops WITHOUT a final model answer.

        The caller always gets something to show, and (optionally) the
        stop reason is stored so the next turn knows what happened.
        """

        result = LLMResult(
            response=f"I stopped before finishing the task. Reason: {reason}",
            message={},
            tool_calls=[],
            thinking=None,
            usage=0,
            raw=None,
        )

        if remember:
            self.memory.step(self._assistant_message_to_event(result))

        self.memory.saveall()

        return result

    def _log_tool_call(
        self,
        call,
    ) -> None:

        self.logger.info(
            f"Tool call → {getattr(call, 'name', 'unknown')} "
            f"| action={getattr(call, 'action', 'execute')} "
            f"| target={getattr(call, 'target', '')} "
            f"| valid={getattr(call, 'valid', False)} "
            f"| approved={getattr(call, 'approved', False)} "
            f"| args={getattr(call, 'args', {})}"
        )

    def _classify_calls(
        self,
        parsed_calls: list,
        iteration: int,
    ) -> tuple[list[int], dict[int, ToolResult]]:
        """
        Classify parsed tool calls into allowed vs blocked.

        Blocking reasons:

            - invalid tool call
            - identical call already inside this same model response
            - identical successful call at the current workspace revision
              (same tool + same arguments)
        """

        allowed_indices: list[int] = []
        blocked_results: dict[int, ToolResult] = {}
        response_seen_keys: set[str] = set()

        for index, call in enumerate(parsed_calls):

            if not getattr(call, "valid", False):
                blocked_results[index] = self._invalid_result(call)
                continue

            key = self._tool_call_key(call)

            # Duplicate inside the same model response.
            if key in response_seen_keys:
                blocked_results[index] = self._duplicate_result(
                    call,
                    "The same call already appears in this model response.",
                )
                continue

            response_seen_keys.add(key)

            # Duplicate against a prior successful call at this revision.
            previous_revision = self._successful_tool_calls.get(key)

            if (
                previous_revision is not None
                and previous_revision == self.workspace_revision
            ):
                blocked_results[index] = self._duplicate_result(
                    call,
                    (
                        "A successful identical call already ran at the "
                        "current workspace revision."
                    ),
                )
                continue

            allowed_indices.append(index)

        return allowed_indices, blocked_results

    def _execute_allowed_calls(
        self,
        raw_tool_calls: list,
        allowed_indices: list[int],
    ) -> tuple[list, list[ToolResult]]:

        if not allowed_indices:
            return [], []

        allowed_raw_calls = [raw_tool_calls[index] for index in allowed_indices]

        executed_calls: list = []
        executed_results: list[ToolResult] = []

        try:
            tool_result = self.tool.execute(allowed_raw_calls)

            raw_executed_calls = tool_result.get("calls", [])
            raw_executed_results = tool_result.get("results", [])

            if isinstance(raw_executed_calls, list):
                executed_calls = raw_executed_calls

            if isinstance(raw_executed_results, list):
                executed_results = raw_executed_results

        except Exception as exc:
            self.logger.error(f"tool execution failed: {exc}")

        return executed_calls, executed_results

    def _apply_result_to_state(
        self,
        call,
        result: ToolResult,
        iteration: int,
    ) -> None:

        self._log_tool_call(call)

        self.agent_state.begin(
            tool_call=call,
            iteration=iteration,
        )

        self.memory.step(self._tool_call_to_event(call))

        self.logger.info(
            f"Tool result ← {result.name} "
            f"| success={result.success} "
            f"| summary={result.summary}"
        )

        self.agent_state.update_from_result(result)

        changed = self.working_set.update(
            tool_call=call,
            result=result,
            iteration=iteration,
        )

        if result.success and changed:
            self.workspace_revision += 1

        if result.success:
            key = self._tool_call_key(call)
            self._successful_tool_calls[key] = self.workspace_revision

        self.memory.step(
            self._tool_result_to_event(
                call,
                result,
            )
        )

    def _check_failure_stuck(
        self,
        call,
        result: ToolResult,
    ) -> str | None:
        """
        Track consecutive identical failure signatures.

        Duplicate blocks are NOT treated as failures here.
        """

        is_duplicate = bool(
            isinstance(result.metadata, dict)
            and result.metadata.get("duplicate_action", False)
        )

        if result.success:
            self._recent_failure_signatures.clear()
            return None

        if is_duplicate:
            return None

        signature = self._failure_signature(
            call,
            result,
        )

        self._recent_failure_signatures.append(signature)

        if len(self._recent_failure_signatures) > self.FAILURE_STUCK_THRESHOLD:
            self._recent_failure_signatures.pop(0)

        if (
            len(self._recent_failure_signatures) >= self.FAILURE_STUCK_THRESHOLD
            and len(set(self._recent_failure_signatures)) == 1
        ):
            return (
                f"STUCK: '{call.name}' failed "
                f"{self.FAILURE_STUCK_THRESHOLD} times in a row with the same "
                f"error. Last error: {result.summary[:200]}"
            )

        return None

    def _execute_tool_calls(
        self,
        llmresult: LLMResult,
        iteration: int,
    ) -> bool:
        """
        Execute model tool calls for one iteration.

        Returns:
            True  -> stop the loop
            False -> continue
        """

        raw_tool_calls = llmresult.tool_calls or []

        if not raw_tool_calls:
            self.logger.info("No tool calls to execute.")
            return False

        self.logger.info(f"Executing {len(raw_tool_calls)} tool call(s)")

        try:
            parsed_calls = self.tool.dispatcher.dispatch(raw_tool_calls)
        except Exception as exc:
            self.logger.error(f"tool dispatch failed: {exc}")
            parsed_calls = []

        if not parsed_calls:
            self.logger.error("No canonical tool calls were produced.")
            return False

        allowed_indices, blocked_results = self._classify_calls(
            parsed_calls,
            iteration=iteration,
        )

        executed_calls, executed_results = self._execute_allowed_calls(
            raw_tool_calls,
            allowed_indices,
        )

        executed_by_original_index: dict[
            int,
            tuple[Any, ToolResult],
        ] = {}

        for position, original_index in enumerate(allowed_indices):

            if position >= len(executed_results):
                break

            result = executed_results[position]

            if not isinstance(result, ToolResult):
                result = self._missing_result(parsed_calls[original_index])

            if position < len(executed_calls):
                canonical_call = executed_calls[position]
            else:
                canonical_call = parsed_calls[original_index]

            executed_by_original_index[original_index] = (
                canonical_call,
                result,
            )

        # Apply every result (blocked and executed) to runtime state.
        for index, parsed_call in enumerate(parsed_calls):

            if index in blocked_results:
                call = parsed_call
                result = blocked_results[index]

            elif index in executed_by_original_index:
                call, result = executed_by_original_index[index]

            else:
                call = parsed_call
                result = self._missing_result(call)

            self._apply_result_to_state(
                call=call,
                result=result,
                iteration=iteration,
            )

            stop_reason = self._check_failure_stuck(
                call,
                result,
            )

            if stop_reason is not None:
                self.logger.error(stop_reason)
                self.agent_state.stop(stop_reason)
                return True

        # Duplicate streak accounting across iterations.
        if blocked_results and not allowed_indices:

            blocked_index = min(blocked_results)

            blocked_key = self._tool_call_key(parsed_calls[blocked_index])

            if blocked_key == self._last_duplicate_key:
                self._duplicate_block_streak += 1
            else:
                self._duplicate_block_streak = 1

            self._last_duplicate_key = blocked_key

        else:
            self._duplicate_block_streak = 0
            self._last_duplicate_key = None

        if self._duplicate_block_streak >= self.DUPLICATE_BLOCK_THRESHOLD:

            reason = (
                f"Repeated identical tool action was blocked "
                f"{self.DUPLICATE_BLOCK_THRESHOLD} times in a row without "
                f"workspace progress."
            )

            self.logger.warning(reason)

            self.agent_state.stop(reason)

            return True

        return False

    def run(
        self,
        user_task: MemoryEvent,
        workspace_directory: str = "EvanaEval",
    ):

        if not isinstance(user_task, MemoryEvent):
            self.logger.error("user_task must be a MemoryEvent.")
            return None

        self._reset_run_state()

        self.logger.info(
            "Starting agent loop | "
            f"max_iterations={self.max_iterations} | "
            f"workspace={workspace_directory}"
        )

        self._persist_user_task(user_task)

        empty_streak = 0

        for iteration in range(self.max_iterations):

            iteration_number = iteration + 1

            self.agent_state.iteration = iteration_number

            self.logger.info(f"Iteration {iteration_number}/{self.max_iterations}")

            llmresult = self._generate_next_action(
                user_task=user_task,
                workspace_directory=workspace_directory,
            )

            if llmresult is None:
                return self._stopped_result(
                    self.agent_state.error or "LLM generation failed.",
                    remember=False,
                )

            self.context.calibrate(llmresult)

            if llmresult.tool_calls:

                empty_streak = 0

                self.memory.step(self._assistant_message_to_event(llmresult))

                should_stop = self._execute_tool_calls(
                    llmresult,
                    iteration=iteration_number,
                )

                if should_stop:
                    return self._stopped_result(
                        self.agent_state.error or "The loop was stopped."
                    )

                continue

            if llmresult.response:

                self.memory.step(self._assistant_message_to_event(llmresult))

                self.agent_state.complete()

                self.memory.saveall()

                return llmresult

            self.logger.warning("LLM produced neither response nor tool calls.")

            empty_streak += 1

            if empty_streak >= self.EMPTY_RESPONSE_THRESHOLD:

                reason = (
                    f"The model returned nothing "
                    f"{self.EMPTY_RESPONSE_THRESHOLD} times in a row."
                )

                self.logger.error(reason)

                self.agent_state.stop(reason)

                return self._stopped_result(reason)

        self.logger.warning("Maximum iterations reached.")

        self.agent_state.stop("Maximum iterations reached.")

        return self._stopped_result("Maximum iterations reached.")

    def _reset_run_state(self) -> None:

        self.agent_state.reset()
        self.working_set.reset()

        self.workspace_revision = 0

        self._successful_tool_calls.clear()

        self._last_duplicate_key = None
        self._duplicate_block_streak = 0

        self._recent_failure_signatures.clear()

    def _persist_user_task(
        self,
        user_task: MemoryEvent,
    ) -> None:

        existing_events = self.memory.get_previous_events(
            k=self.EVENT_HISTORY_WINDOW,
        )

        if self._contains_event(
            existing_events,
            user_task,
        ):
            return

        if not self.memory.step(user_task):
            self.logger.error("Failed to store user task.")

    def _generate_next_action(
        self,
        user_task: MemoryEvent,
        workspace_directory: str,
    ) -> LLMResult | None:

        events = self.memory.get_previous_events(
            k=self.EVENT_HISTORY_WINDOW,
        )

        context = self.context.get_context(
            events=events,
            user_task=user_task,
            agent_state=self.agent_state,
            working_set=self.working_set.context(),
            observation=self.working_set.observation_context(),
            recent_actions=self.working_set.recent_actions_context(),
            workspace_directory=workspace_directory,
        )

        try:
            llmresult = self.llm.generate(
                context,
                tools=self.tool_definitions,
            )
        except Exception as exc:
            self.logger.error(f"LLM generation failed: {exc}")
            self.agent_state.fail(str(exc))
            return None

        if llmresult is None:
            self.logger.error("LLM returned None.")
            self.agent_state.fail("LLM returned None.")
            return None

        return llmresult

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
