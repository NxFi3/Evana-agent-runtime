#src/Agent/CompletionEvaluator.py

from dataclasses import dataclass
from typing import Any, List, Dict
import json

from src.Engine.LlmProviderManager import LlmProvider
from src.Engine.providers.LLMResult import LLMResult
from src.Utils.logger import get_logger


logger = get_logger("[COMPLETIONEVALUATOR]")


@dataclass
class CompletionEvaluation:
    complete: bool
    feedback: str = ""


class CompletionEvaluator:

    def __init__(
        self,
        llm_provider: LlmProvider,
    ) -> None:

        self.llm_provider = llm_provider

    def _event_to_text(
        self,
        event: Any,
    ) -> str:

        event_type = getattr(
            event,
            "event_type",
            "unknown",
        )

        content = getattr(
            event,
            "content",
            "",
        )

        return (
            f"[{event_type}] "
            f"{str(content or '')}"
        )

    def _build_prompt(
        self,
        task: str,
        latest_response: str,
        events: List[Any],
    ) -> List[Dict[str, Any]]:

        history_text = "\n".join(
            self._event_to_text(event)
            for event in events
        )

        judge_prompt = f"""
You are a completion evaluator for an autonomous software engineering agent.

Determine whether the agent has actually completed the user's original task.

Do NOT judge based only on the agent's claim that it is finished.

Consider:
- The original task requirements.
- What the agent actually did.
- Tool calls and tool results.
- Execution and test evidence when relevant.
- Whether important requested functionality remains unfinished.
- Whether the agent stopped prematurely.

Return ONLY valid JSON in exactly this format:

{{
  "complete": true,
  "feedback": ""
}}

or:

{{
  "complete": false,
  "feedback": "Briefly explain what remains to be done."
}}

Rules:
- complete=true only when the requested task is actually complete.
- complete=false when any important requested work remains.
- Keep feedback concise and actionable.
- Do not invent missing evidence.
- Do not require a specific tool unless the task actually requires it.
- Ignore whether the agent used the "correct" implementation style; judge the result against the user's request.

ORIGINAL TASK:
{task}

LATEST AGENT RESPONSE:
{latest_response}

RECENT EXECUTION HISTORY:
{history_text}
""".strip()

        return [
            {
                "role": "system",
                "content": (
                    "You are a strict but practical "
                    "software-task completion judge."
                ),
            },
            {
                "role": "user",
                "content": judge_prompt,
            },
        ]

    def evaluate(
        self,
        task: str,
        latest_response: str,
        events: List[Any],
    ) -> CompletionEvaluation:

        messages = self._build_prompt(
            task=task,
            latest_response=latest_response,
            events=events,
        )

        try:

            result = self.llm_provider.generate(
                messages=messages,
                tools=[],
                images=[],
            )

        except Exception as e:

            logger.error(
                f"Completion evaluation failed: {e}"
            )

            # Fail closed:
            # if the judge itself fails, do not claim completion.
            return CompletionEvaluation(
                complete=False,
                feedback=(
                    "Completion evaluation failed. "
                    "Continue working and verify the task."
                ),
            )

        if not isinstance(
            result,
            LLMResult,
        ):

            logger.error(
                "Completion evaluator received "
                "an invalid LLM result."
            )

            return CompletionEvaluation(
                complete=False,
                feedback=(
                    "Completion evaluation failed. "
                    "Continue working and verify the task."
                ),
            )

        raw_response = (
            result.response or ""
        ).strip()

        if not raw_response:
            return CompletionEvaluation(
                complete=False,
                feedback=(
                    "No completion verdict was produced. "
                    "Continue working."
                ),
            )

        try:

            parsed = json.loads(
                raw_response
            )

        except json.JSONDecodeError:

            logger.warning(
                "Completion evaluator returned "
                "invalid JSON."
            )

            return CompletionEvaluation(
                complete=False,
                feedback=(
                    "The completion verdict was invalid. "
                    "Continue working and verify the task."
                ),
            )

        if not isinstance(
            parsed,
            dict,
        ):

            return CompletionEvaluation(
                complete=False,
                feedback=(
                    "The completion verdict had an "
                    "invalid structure. Continue working."
                ),
            )

        complete = parsed.get(
            "complete",
            False,
        )

        feedback = parsed.get(
            "feedback",
            "",
        )

        if not isinstance(
            complete,
            bool,
        ):

            complete = False

        if not isinstance(
            feedback,
            str,
        ):

            feedback = str(
                feedback or ""
            )

        return CompletionEvaluation(
            complete=complete,
            feedback=feedback.strip(),
        )