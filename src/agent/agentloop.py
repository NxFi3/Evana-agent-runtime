from __future__ import annotations

import json

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

        # Increases only after a successful workspace mutation.
        self.workspace_revision = 0

        # canonical_tool_call -> workspace revision
        # at which the exact call last succeeded.
        self._successful_tool_calls: dict[
            str,
            int,
        ] = {}

        self._last_duplicate_key: str | None = None
        self._duplicate_block_streak = 0

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

    # ------------------------------------------------------------------
    # EVENTS
    # ------------------------------------------------------------------

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
        result: ToolResult,
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

    # ------------------------------------------------------------------
    # TOOL CALL IDENTITY
    # ------------------------------------------------------------------

    @staticmethod
    def _tool_call_key(
        call,
    ) -> str:

        payload = {
            "name": str(
                getattr(
                    call,
                    "name",
                    "",
                )
            )
            .strip()
            .lower(),
            "args": getattr(
                call,
                "args",
                {},
            )
            or {},
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

    # ------------------------------------------------------------------
    # FALLBACK RESULTS
    # ------------------------------------------------------------------

    @staticmethod
    def _duplicate_result(
        call,
        reason: str,
    ) -> ToolResult:

        tool_name = str(
            getattr(
                call,
                "name",
                "unknown",
            )
        ).strip()

        target = str(
            getattr(
                call,
                "target",
                "",
            )
        ).strip()

        if target:
            summary = (
                f"Duplicate action blocked for "
                f"{tool_name} on {target}. "
                f"{reason}"
            )
        else:
            summary = f"Duplicate action blocked for " f"{tool_name}. " f"{reason}"

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

        tool_name = str(
            getattr(
                call,
                "name",
                "unknown",
            )
        ).strip()

        return ToolResult(
            success=False,
            name=tool_name,
            content={
                "success": False,
                "error": {
                    "type": "missing_tool_result",
                    "message": (
                        "ToolManager did not return " "a result for this tool call."
                    ),
                },
            },
            metadata={},
            summary=("Tool execution produced no result."),
        )

    # ------------------------------------------------------------------
    # LOGGING
    # ------------------------------------------------------------------

    def _log_tool_call(
        self,
        call,
    ) -> None:

        tool_name = str(
            getattr(
                call,
                "name",
                "unknown",
            )
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

    # ------------------------------------------------------------------
    # TOOL EXECUTION
    # ------------------------------------------------------------------

    def _execute_tool_calls(
        self,
        llmresult: LLMResult,
        iteration: int,
    ) -> bool:
        """
        Execute model tool calls.

        Important:
            The model provides raw provider-specific tool call objects.

            ToolManager -> ToolDispatcher converts them into canonical
            ToolCall objects.

            All runtime state, logging, memory, duplicate detection,
            and WorkingSet updates MUST use those canonical ToolCall
            objects, not the raw provider objects.

        Returns:
            True  -> stop the loop
            False -> continue
        """

        raw_tool_calls = llmresult.tool_calls or []

        if not raw_tool_calls:
            self.logger.info("No tool calls to execute.")
            return False

        self.logger.info(f"Executing " f"{len(raw_tool_calls)} " f"tool call(s)")

        # --------------------------------------------------------------
        # STEP 1
        # Filter duplicates BEFORE execution.
        #
        # raw_tool_calls are provider-specific, but we can still use the
        # normalized key only if the provider exposes the same structure.
        #
        # To avoid relying on provider internals, duplicate detection is
        # finalized after ToolManager normalization.
        # --------------------------------------------------------------

        # We first dispatch through ToolManager for canonical calls.
        #
        # ToolManager already:
        #   raw provider call
        #        ↓
        #   ToolDispatcher
        #        ↓
        #   canonical ToolCall
        #
        # We therefore need canonical calls BEFORE deciding what should
        # execute. ToolManager's public API currently combines parsing
        # and execution, so we perform a lightweight first dispatch here
        # through its dispatcher.
        try:
            parsed_calls = self.tool.dispatcher.dispatch(raw_tool_calls)
        except Exception as exc:
            self.logger.error(f"tool dispatch failed: {exc}")

            parsed_calls = []

        if not parsed_calls:
            self.logger.error("No canonical tool calls were produced.")

            return False

        # --------------------------------------------------------------
        # STEP 2
        # Determine which canonical calls are duplicates.
        # --------------------------------------------------------------

        allowed_indices: list[int] = []

        blocked_results: dict[
            int,
            ToolResult,
        ] = {}

        response_seen_keys: set[str] = set()

        for index, call in enumerate(parsed_calls):

            if not getattr(
                call,
                "valid",
                False,
            ):

                blocked_results[index] = ToolResult(
                    success=False,
                    name=str(
                        getattr(
                            call,
                            "name",
                            "unknown",
                        )
                    ),
                    content={
                        "success": False,
                        "error": {
                            "type": "invalid_tool_call",
                            "message": ("Invalid tool call."),
                        },
                    },
                    metadata={},
                    summary=("Invalid tool call."),
                )

                continue

            key = self._tool_call_key(call)

            if key in response_seen_keys:

                blocked_results[index] = self._duplicate_result(
                    call,
                    ("The same call already " "appears in this model response."),
                )

                continue

            response_seen_keys.add(key)

            previous_revision = self._successful_tool_calls.get(key)

            if (
                previous_revision is not None
                and previous_revision == self.workspace_revision
            ):

                blocked_results[index] = self._duplicate_result(
                    call,
                    (
                        "A successful identical call "
                        "already ran at the current "
                        "workspace revision. "
                        "Use the existing observation "
                        "or working set, or perform "
                        "a different action."
                    ),
                )

                continue

            allowed_indices.append(index)

        # --------------------------------------------------------------
        # STEP 3
        # Execute only allowed canonical calls.
        #
        # ToolManager.dispatch() will parse them AGAIN because its public
        # execute() API accepts raw calls. We therefore intentionally pass
        # the original raw calls corresponding to allowed indices.
        #
        # The important part is that after ToolManager execution we use
        # ToolManager's returned canonical calls.
        # --------------------------------------------------------------

        allowed_raw_calls = [raw_tool_calls[index] for index in allowed_indices]

        executed_calls = []
        executed_results = []

        if allowed_raw_calls:

            try:
                tool_result = self.tool.execute(allowed_raw_calls)

                raw_executed_calls = tool_result.get(
                    "calls",
                    [],
                )

                raw_executed_results = tool_result.get(
                    "results",
                    [],
                )

                if isinstance(
                    raw_executed_calls,
                    list,
                ):
                    executed_calls = raw_executed_calls

                if isinstance(
                    raw_executed_results,
                    list,
                ):
                    executed_results = raw_executed_results

            except Exception as exc:
                self.logger.error(f"tool execution failed: {exc}")

        # --------------------------------------------------------------
        # STEP 4
        # Build index -> canonical ToolCall / ToolResult mapping.
        # --------------------------------------------------------------

        executed_by_original_index: dict[
            int,
            tuple[
                object,
                ToolResult,
            ],
        ] = {}

        for position, original_index in enumerate(allowed_indices):

            if position >= len(executed_results):
                break

            result = executed_results[position]

            if not isinstance(
                result,
                ToolResult,
            ):
                result = self._missing_result(parsed_calls[original_index])

            if position < len(executed_calls):
                canonical_call = executed_calls[position]
            else:
                canonical_call = parsed_calls[original_index]

            executed_by_original_index[original_index] = (
                canonical_call,
                result,
            )

        # --------------------------------------------------------------
        # STEP 5
        # Process every canonical call in original order.
        # --------------------------------------------------------------

        for index, parsed_call in enumerate(parsed_calls):

            # Duplicate / invalid result.
            if index in blocked_results:

                call = parsed_call
                result = blocked_results[index]

            # Successfully dispatched to ToolManager.
            elif index in executed_by_original_index:

                call, result = executed_by_original_index[index]

            # Something disappeared between dispatch and execution.
            else:

                call = parsed_call
                result = self._missing_result(call)

            self._log_tool_call(call)

            self.agent_state.begin(
                tool_call=call,
                iteration=iteration,
            )

            self.memory.step(self._tool_call_to_event(call))

            self.logger.info(
                f"Tool result ← "
                f"{result.name} "
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

            self.memory.step(self._tool_result_to_event(result))

        # --------------------------------------------------------------
        # STEP 6
        # Repeated duplicate-loop breaker.
        # --------------------------------------------------------------

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

        if self._duplicate_block_streak >= 2:

            reason = (
                "Repeated identical tool action "
                "was blocked twice without "
                "workspace progress."
            )

            self.logger.warning(reason)

            self.agent_state.stop(reason)

            return True

        return False

    # ------------------------------------------------------------------
    # MAIN LOOP
    # ------------------------------------------------------------------

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

        # Fresh execution state.
        self.agent_state.reset()

        self.working_set.reset()

        self.workspace_revision = 0

        self._successful_tool_calls.clear()

        self._last_duplicate_key = None

        self._duplicate_block_streak = 0

        self.logger.info(
            "Starting agent loop | "
            f"max_iterations={self.max_iterations} | "
            f"workspace={workspace_directory}"
        )

        # Persist user task once.
        existing_events = self.memory.get_previous_events(k=20)

        if not self._contains_event(
            existing_events,
            user_task,
        ):

            if not self.memory.step(user_task):

                self.logger.error("Failed to store user task.")

                return None

        # --------------------------------------------------------------
        # AGENT LOOP
        # --------------------------------------------------------------

        for iteration in range(self.max_iterations):

            iteration_number = iteration + 1

            self.agent_state.iteration = iteration_number

            self.logger.info(
                f"Iteration " f"{iteration_number}/" f"{self.max_iterations}"
            )

            events = self.memory.get_previous_events(k=20)

            context = self.context.get_context(
                events=events,
                user_task=user_task,
                agent_state=self.agent_state,
                working_set=(self.working_set.context()),
                observation=(self.working_set.observation_context()),
                recent_actions=(self.working_set.recent_actions_context()),
                workspace_directory=(workspace_directory),
            )

            try:

                llmresult = self.llm.generate(
                    context,
                    tools=self.tool_definitions,
                )

            except Exception as exc:

                self.logger.error(f"LLM generation failed: {exc}")

                self.agent_state.fail(str(exc))

                self.memory.saveall()

                return None

            if llmresult is None:

                self.logger.error("LLM returned None.")

                self.agent_state.fail("LLM returned None.")

                self.memory.saveall()

                return None

            self.context.calibrate(llmresult)

            # ----------------------------------------------------------
            # TOOL CALL
            # ----------------------------------------------------------

            if llmresult.tool_calls:

                self.memory.step(self._assistant_message_to_event(llmresult))

                should_stop = self._execute_tool_calls(
                    llmresult,
                    iteration=iteration_number,
                )

                if should_stop:

                    self.memory.saveall()

                    return None

                continue

            # ----------------------------------------------------------
            # FINAL RESPONSE
            # ----------------------------------------------------------

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

    # ------------------------------------------------------------------
    # MEMORY HELPERS
    # ------------------------------------------------------------------

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
