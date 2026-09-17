from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolResult:
    """
    Canonical result returned by every tool.

    `content` and `metadata` remain backward-compatible with the
    existing runtime.

    The runtime additionally derives:
        - summary
        - evidence
        - effects

    This keeps ContextBuilder generic. Tools describe what happened;
    the context layer only consumes the normalized result.
    """

    success: bool
    name: str
    content: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    summary: str = ""
    evidence: dict[str, Any] = field(default_factory=dict)
    effects: list[dict[str, str]] = field(default_factory=list)

    MAX_SUMMARY_CHARS = 400
    MAX_EVIDENCE_CHARS = 6000
    MAX_FILE_EVIDENCE_CHARS = 5000
    MAX_STDOUT_CHARS = 4000
    MAX_STDERR_CHARS = 2000
    MAX_GENERIC_CONTENT_CHARS = 4000

    def __post_init__(self) -> None:
        if not isinstance(self.content, dict):
            self.content = {
                "value": self.content,
            }

        if not isinstance(self.metadata, dict):
            self.metadata = {}

        if not self.summary:
            self.summary = self._derive_summary()

        self.summary = self._truncate_text(
            self.summary,
            self.MAX_SUMMARY_CHARS,
        )

        if not self.evidence:
            self.evidence = self._derive_evidence()

        if not self.effects:
            self.effects = self._derive_effects()

        if self.effects:
            self.metadata["effects"] = self.effects

    @staticmethod
    def _truncate_text(
        value: str,
        limit: int,
    ) -> str:
        value = str(value)

        if len(value) <= limit:
            return value

        if limit <= 32:
            return value[:limit]

        return (
            value[: limit - 32].rstrip()
            + "\n"
            + f"... {len(value) - (limit - 32)} chars omitted ..."
        )

    @classmethod
    def _safe_json(
        cls,
        value: Any,
        limit: int,
    ) -> str:
        try:
            serialized = json.dumps(
                value,
                ensure_ascii=False,
                default=str,
            )
        except Exception:
            serialized = str(value)

        return cls._truncate_text(
            serialized,
            limit,
        )

    def _derive_summary(self) -> str:
        content = self.content

        explicit_summary = content.get("summary")

        if explicit_summary:
            return str(explicit_summary)

        metadata_summary = self.metadata.get("summary")

        if metadata_summary:
            return str(metadata_summary)

        error = content.get("error")

        if isinstance(error, dict):
            message = error.get("message")

            if message:
                return f"Tool failed: {message}"

        if isinstance(error, str) and error.strip():
            return f"Tool failed: {error.strip()}"

        path = content.get("path")

        if path and content.get("type") == "file" and "content" in content:
            if self.success:
                return f"Read file {path}."

            return f"Failed to read file {path}."

        files = content.get("files")

        if isinstance(files, list):
            if self.success:
                return f"Processed {len(files)} file operation(s)."

            return f"File operation failed for {len(files)} operation(s)."

        if "exit_code" in content:
            exit_code = content.get("exit_code")

            if self.success:
                return f"Command completed successfully (exit_code={exit_code})."

            return f"Command failed (exit_code={exit_code})."

        if self.success:
            return f"{self.name} completed successfully."

        return f"{self.name} failed."

    def _derive_evidence(self) -> dict[str, Any]:
        content = self.content

        # File read / inspect result.
        path = content.get("path")

        if path and "content" in content:
            file_content = content.get("content")

            evidence: dict[str, Any] = {
                "type": content.get("type", "file"),
                "path": str(path),
            }

            if isinstance(file_content, str):
                evidence["content"] = self._truncate_text(
                    file_content,
                    self.MAX_FILE_EVIDENCE_CHARS,
                )
            else:
                evidence["content"] = str(file_content)

            for key in (
                "start_line",
                "end_line",
                "lines_requested",
                "lines_returned",
                "total_lines",
                "truncated",
            ):
                if key in content:
                    evidence[key] = content[key]

            return evidence

        # Command execution result.
        if any(
            key in content
            for key in (
                "exit_code",
                "stdout",
                "stderr",
                "timed_out",
            )
        ):
            evidence = {}

            if "command" in content:
                evidence["command"] = content["command"]

            if "workdir" in content:
                evidence["workdir"] = content["workdir"]

            if "exit_code" in content:
                evidence["exit_code"] = content["exit_code"]

            if "timed_out" in content:
                evidence["timed_out"] = content["timed_out"]

            if "duration_ms" in content:
                evidence["duration_ms"] = content["duration_ms"]

            stdout = content.get("stdout")

            if isinstance(stdout, str) and stdout:
                evidence["stdout"] = self._truncate_text(
                    stdout,
                    self.MAX_STDOUT_CHARS,
                )

            stderr = content.get("stderr")

            if isinstance(stderr, str) and stderr:
                evidence["stderr"] = self._truncate_text(
                    stderr,
                    self.MAX_STDERR_CHARS,
                )

            return evidence

        # Multi-file patch / filesystem result.
        files = content.get("files")

        if isinstance(files, list):
            normalized_files: list[dict[str, Any]] = []

            for item in files:
                if not isinstance(item, dict):
                    continue

                normalized: dict[str, Any] = {}

                for key in (
                    "operation",
                    "path",
                    "target",
                    "added",
                    "removed",
                ):
                    if key in item:
                        normalized[key] = item[key]

                file_content = item.get("content")

                if isinstance(file_content, str) and file_content:
                    normalized["content_preview"] = self._truncate_text(
                        file_content,
                        1600,
                    )

                if normalized:
                    normalized_files.append(normalized)

            return {
                "files": normalized_files,
            }

        # Structured error.
        if "error" in content:
            error_value = content.get("error")

            if isinstance(error_value, dict):
                return {
                    "error": error_value,
                }

            return {
                "error": str(error_value),
            }

        # Generic fallback.
        safe_content = dict(content)

        for key in (
            "stdout",
            "stderr",
            "content",
            "files",
        ):
            safe_content.pop(key, None)

        if not safe_content:
            return {}

        return {
            "data": self._safe_json(
                safe_content,
                self.MAX_GENERIC_CONTENT_CHARS,
            )
        }

    # ------------------------------------------------------------------
    # EFFECTS
    # ------------------------------------------------------------------

    def _derive_effects(self) -> list[dict[str, str]]:
        effects: list[dict[str, str]] = []

        metadata_effects = self.metadata.get("effects")

        if isinstance(metadata_effects, list):
            for item in metadata_effects:
                normalized = self._normalize_effect(item)

                if normalized:
                    effects.append(normalized)

            if effects:
                return effects

        files = self.content.get("files")

        if isinstance(files, list):
            for item in files:
                if not isinstance(item, dict):
                    continue

                normalized = self._normalize_effect(
                    {
                        "action": item.get(
                            "operation",
                            "",
                        ),
                        "target": (item.get("path") or item.get("target") or ""),
                    }
                )

                if normalized:
                    effects.append(normalized)

            if effects:
                return effects

        path = self.content.get("path") or self.content.get("target")

        if path:
            effects.append(
                {
                    "action": "inspect",
                    "target": str(path),
                }
            )

        return effects

    @staticmethod
    def _normalize_effect(
        value: Any,
    ) -> dict[str, str] | None:
        if not isinstance(value, dict):
            return None

        action = (
            str(
                value.get(
                    "action",
                    "",
                )
            )
            .strip()
            .lower()
        )

        target = str(
            value.get(
                "target",
                "",
            )
        ).strip()

        if not action:
            return None

        return {
            "action": action,
            "target": target,
        }

    def to_observation(self) -> dict[str, Any]:
        return {
            "tool": self.name,
            "success": self.success,
            "summary": self.summary,
            "evidence": self.evidence,
            "effects": self.effects,
        }
