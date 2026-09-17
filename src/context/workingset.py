from __future__ import annotations

from collections import OrderedDict
from typing import Any

from src.models.ToolCall import ToolCall
from src.models.ToolResult import ToolResult


class WorkingSet:
    """
    Compact model-facing execution state.

    Memory keeps the complete runtime history.
    WorkingSet keeps only the durable facts needed for the next decision.
    """

    MUTATING_ACTIONS = {
        "create",
        "add",
        "modify",
        "update",
        "delete",
        "remove",
        "write",
        "rename",
        "move",
    }

    MAX_ARTIFACTS = 8
    MAX_ARTIFACT_PREVIEW_CHARS = 1800

    MAX_FACTS = 12
    MAX_UNRESOLVED = 8
    MAX_RECENT_ACTIONS = 12
    MAX_OBSERVATIONS = 4

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self.artifacts: OrderedDict[str, dict[str, Any]] = OrderedDict()

        self.facts: list[str] = []

        self.unresolved: list[str] = []

        self.verification: dict[str, Any] = {}

        self.recent_actions: list[dict[str, Any]] = []

        self.observations: list[dict[str, Any]] = []

    def update(
        self,
        tool_call: ToolCall,
        result: ToolResult,
        iteration: int,
    ) -> bool:
        """
        Update the working set from one tool execution.

        Returns True when the result represents a workspace mutation.
        """

        if not isinstance(result, ToolResult):
            return False

        tool_name = str(
            getattr(
                tool_call,
                "name",
                result.name,
            )
        ).strip()

        action = str(
            getattr(
                tool_call,
                "action",
                "execute",
            )
        ).strip()

        target = str(
            getattr(
                tool_call,
                "target",
                "",
            )
        ).strip()

        self._record_recent_action(
            tool_name=tool_name,
            action=action,
            target=target,
            result=result,
            iteration=iteration,
        )

        self._record_observation(result)

        for effect in result.effects:
            self._apply_effect(
                effect=effect,
                result=result,
                iteration=iteration,
            )

        self._update_verification(
            tool_call=tool_call,
            result=result,
        )

        self._update_facts(
            tool_call=tool_call,
            result=result,
        )

        if result.success:
            self._clear_related_failure(target)
        else:
            self._record_failure(
                target=target,
                result=result,
            )

        return self._result_changes_workspace(
            tool_call=tool_call,
            result=result,
        )

    def _record_recent_action(
        self,
        tool_name: str,
        action: str,
        target: str,
        result: ToolResult,
        iteration: int,
    ) -> None:
        item = {
            "iteration": iteration,
            "tool": tool_name,
            "action": action,
            "target": target,
            "success": result.success,
            "summary": result.summary,
        }

        self.recent_actions.append(item)

        if len(self.recent_actions) > self.MAX_RECENT_ACTIONS:
            del self.recent_actions[
                : len(self.recent_actions) - self.MAX_RECENT_ACTIONS
            ]

    def _record_observation(
        self,
        result: ToolResult,
    ) -> None:
        observation = result.to_observation()

        self.observations.append(observation)

        if len(self.observations) > self.MAX_OBSERVATIONS:
            del self.observations[: len(self.observations) - self.MAX_OBSERVATIONS]

    def _apply_effect(
        self,
        effect: dict[str, str],
        result: ToolResult,
        iteration: int,
    ) -> None:
        action = (
            str(
                effect.get(
                    "action",
                    "",
                )
            )
            .strip()
            .lower()
        )

        target = str(
            effect.get(
                "target",
                "",
            )
        ).strip()

        if not target:
            return

        if target in self.artifacts:
            artifact = dict(self.artifacts[target])
        else:
            artifact = {
                "status": "unknown",
                "known": False,
            }

        artifact["last_operation"] = action
        artifact["last_iteration"] = iteration

        preview = self._extract_preview(
            result=result,
            target=target,
        )

        if action in {
            "inspect",
            "read",
        }:
            artifact["status"] = "known"
            artifact["known"] = True

            if preview:
                artifact["preview"] = preview
                artifact["preview_truncated"] = True

        elif action in {
            "create",
            "add",
        }:
            artifact["status"] = "created"
            artifact["known"] = bool(preview)

            if preview:
                artifact["preview"] = preview
                artifact["preview_truncated"] = True

        elif action in {
            "modify",
            "update",
            "write",
        }:
            artifact["status"] = "modified"
            artifact["known"] = bool(preview)

            if preview:
                artifact["preview"] = preview
                artifact["preview_truncated"] = True
            else:
                artifact.pop(
                    "preview",
                    None,
                )
                artifact.pop(
                    "preview_truncated",
                    None,
                )

        elif action in {
            "delete",
            "remove",
        }:
            artifact["status"] = "deleted"
            artifact["known"] = False

            artifact.pop(
                "preview",
                None,
            )

            artifact.pop(
                "preview_truncated",
                None,
            )

        else:
            artifact["status"] = action

        self._touch_artifact(
            target=target,
            artifact=artifact,
        )

    def _touch_artifact(
        self,
        target: str,
        artifact: dict[str, Any],
    ) -> None:
        if target in self.artifacts:
            del self.artifacts[target]

        self.artifacts[target] = artifact

        while len(self.artifacts) > self.MAX_ARTIFACTS:
            self.artifacts.popitem(last=False)

    def _extract_preview(
        self,
        result: ToolResult,
        target: str,
    ) -> str:
        evidence = result.evidence

        if not isinstance(evidence, dict):
            return ""

        evidence_path = str(
            evidence.get(
                "path",
                "",
            )
        ).strip()

        if (
            evidence_path
            and evidence_path == target
            and isinstance(
                evidence.get("content"),
                str,
            )
        ):
            return self._truncate(
                evidence["content"],
                self.MAX_ARTIFACT_PREVIEW_CHARS,
            )

        files = result.content.get("files")

        if not isinstance(files, list):
            return ""

        for item in files:
            if not isinstance(item, dict):
                continue

            item_target = str(item.get("path") or item.get("target") or "").strip()

            if item_target != target:
                continue

            content = item.get("content")

            if isinstance(content, str) and content:
                return self._truncate(
                    content,
                    self.MAX_ARTIFACT_PREVIEW_CHARS,
                )

        return ""

    def _update_verification(
        self,
        tool_call: ToolCall,
        result: ToolResult,
    ) -> None:
        content = result.content

        if not isinstance(content, dict):
            return

        if "exit_code" not in content:
            return

        stdout = content.get("stdout", "")
        stderr = content.get("stderr", "")

        output_parts: list[str] = []

        if isinstance(stdout, str) and stdout.strip():
            output_parts.append(stdout.strip())

        if isinstance(stderr, str) and stderr.strip():
            output_parts.append(stderr.strip())

        output = "\n".join(output_parts)

        self.verification = {
            "tool": str(
                getattr(
                    tool_call,
                    "name",
                    result.name,
                )
            ),
            "success": result.success,
            "exit_code": content.get("exit_code"),
            "timed_out": content.get(
                "timed_out",
                False,
            ),
            "duration_ms": content.get("duration_ms"),
            "output_excerpt": self._truncate(
                output,
                1400,
            ),
        }

    def _update_facts(
        self,
        tool_call: ToolCall,
        result: ToolResult,
    ) -> None:
        if not result.summary:
            return

        fact = str(result.summary).strip()

        if not fact:
            return

        if fact in self.facts:
            self.facts.remove(fact)

        self.facts.append(fact)

        if len(self.facts) > self.MAX_FACTS:
            del self.facts[: len(self.facts) - self.MAX_FACTS]

    def _record_failure(
        self,
        target: str,
        result: ToolResult,
    ) -> None:
        message = result.summary.strip()

        if not message:
            return

        if target:
            message = f"{target}: {message}"

        if message in self.unresolved:
            self.unresolved.remove(message)

        self.unresolved.append(message)

        if len(self.unresolved) > self.MAX_UNRESOLVED:
            del self.unresolved[: len(self.unresolved) - self.MAX_UNRESOLVED]

    def _clear_related_failure(
        self,
        target: str,
    ) -> None:
        if not target:
            return

        normalized_target = target.strip()

        self.unresolved = [
            item
            for item in self.unresolved
            if not item.startswith(f"{normalized_target}:")
        ]

    def _result_changes_workspace(
        self,
        tool_call: ToolCall,
        result: ToolResult,
    ) -> bool:
        if not result.success:
            return False

        call_action = (
            str(
                getattr(
                    tool_call,
                    "action",
                    "",
                )
            )
            .strip()
            .lower()
        )

        if call_action in self.MUTATING_ACTIONS:
            return True

        for effect in result.effects:
            action = (
                str(
                    effect.get(
                        "action",
                        "",
                    )
                )
                .strip()
                .lower()
            )

            if action in self.MUTATING_ACTIONS:
                return True

        return bool(
            result.metadata.get(
                "workspace_changed",
                False,
            )
        )

    def context(self) -> dict[str, Any]:
        return {
            "artifacts": dict(self.artifacts),
            "verification": dict(self.verification),
            "facts": list(self.facts),
            "unresolved": list(self.unresolved),
        }

    def observation_context(self) -> dict[str, Any]:
        return {
            "items": list(self.observations),
        }

    def recent_actions_context(self) -> dict[str, Any]:
        return {
            "items": list(self.recent_actions),
        }

    @staticmethod
    def _truncate(
        value: str,
        limit: int,
    ) -> str:
        value = str(value)

        if len(value) <= limit:
            return value

        return (
            value[: limit - 40].rstrip()
            + "\n"
            + f"... {len(value) - (limit - 40)} chars omitted ..."
        )
