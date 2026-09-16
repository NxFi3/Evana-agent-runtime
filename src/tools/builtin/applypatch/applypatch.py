from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.tools.Tool import Tool
from src.models.ToolResult import ToolResult


@dataclass
class PatchOperation:
    operation: str
    path: str
    hunks: list[list[str]]
    content: str | None = None


class ApplyPatch(Tool):
    """
    Apply Codex-style file patches.

    Supported operations:

        *** Add File: path
        *** Update File: path
        *** Delete File: path

    Example:

        *** Begin Patch
        *** Update File: src/foo.py
        @@
         def hello():
        -    return "old"
        +    return "new"
        *** End Patch
    """

    name = "apply_patch"

    description = (
        "Apply a patch to one or more text files. "
        "Supports adding, updating, and deleting files. "
        "Update hunks use exact context matching. "
        "The operation fails instead of guessing when the patch "
        "does not match exactly. Multiple file operations are allowed "
        "in a single patch."
    )

    parameters = {
        "type": "object",
        "properties": {
            "patch": {
                "type": "string",
                "description": (
                    "Complete patch text using this format:\n"
                    "*** Begin Patch\n"
                    "*** Update File: path/to/file.py\n"
                    "@@\n"
                    " context line\n"
                    "-old line\n"
                    "+new line\n"
                    "*** Add File: path/to/new.py\n"
                    "+content line\n"
                    "*** Delete File: path/to/remove.py\n"
                    "*** End Patch\n\n"
                    "Use exact file context for update operations."
                ),
            }
        },
        "required": ["patch"],
        "additionalProperties": False,
    }

    _BEGIN = "*** Begin Patch"
    _END = "*** End Patch"

    _UPDATE = "*** Update File: "
    _ADD = "*** Add File: "
    _DELETE = "*** Delete File: "

    def execute(self, patch: str) -> ToolResult:
        """
        Execute a single apply_patch call.

        ToolManager calls this as:

            tool.execute(**toolcall.args)

        Therefore the tool-call argument must be:

            {"patch": "..."}
        """

        if not isinstance(patch, str):
            return self._failure(
                error_type="invalid_argument",
                message="patch must be a string.",
            )

        if not patch.strip():
            return self._failure(
                error_type="invalid_patch",
                message="Patch cannot be empty.",
            )

        try:
            operations = self._parse_patch(patch)
        except ValueError as exc:
            return self._failure(
                error_type="parse_error",
                message=str(exc),
            )

        if not operations:
            return self._failure(
                error_type="invalid_patch",
                message="Patch contains no file operations.",
            )

        try:
            plan = self._build_plan(operations)
        except ValueError as exc:
            return self._failure(
                error_type="validation_error",
                message=str(exc),
            )

        try:
            results = self._apply_plan(plan)
        except OSError as exc:
            return self._failure(
                error_type="filesystem_error",
                message=str(exc),
            )
        except Exception as exc:
            return self._failure(
                error_type="application_error",
                message=str(exc),
            )

        files_changed = len(results)
        added = sum(item["added"] for item in results)
        removed = sum(item["removed"] for item in results)

        return self._success(
            summary=(
                f"Applied patch to {files_changed} file(s): "
                f"{added} addition(s), {removed} deletion(s)."
            ),
            files=results,
            statistics={
                "files_changed": files_changed,
                "added": added,
                "removed": removed,
            },
        )

    # PATCH PARSING
    def _parse_patch(self, patch: str) -> list[PatchOperation]:
        lines = patch.splitlines()

        if not lines:
            raise ValueError("Patch is empty.")

        if lines[0].strip() != self._BEGIN:
            raise ValueError(f"Patch must start with '{self._BEGIN}'.")

        if lines[-1].strip() != self._END:
            raise ValueError(f"Patch must end with '{self._END}'.")

        operations: list[PatchOperation] = []

        i = 1

        while i < len(lines) - 1:
            line = lines[i]

            if not line.strip():
                i += 1
                continue

            # UPDATE
            if line.startswith(self._UPDATE):
                path = line[len(self._UPDATE) :].strip()

                if not path:
                    raise ValueError("Update File path cannot be empty.")

                i += 1

                hunks, i = self._parse_hunks(lines, i)

                if not hunks:
                    raise ValueError(f"Update File '{path}' has no hunks.")

                operations.append(
                    PatchOperation(
                        operation="update",
                        path=path,
                        hunks=hunks,
                    )
                )

                continue

            # ADD
            if line.startswith(self._ADD):
                path = line[len(self._ADD) :].strip()

                if not path:
                    raise ValueError("Add File path cannot be empty.")

                i += 1

                content_lines: list[str] = []

                while i < len(lines) - 1:
                    current = lines[i]

                    if (
                        current.startswith(self._UPDATE)
                        or current.startswith(self._ADD)
                        or current.startswith(self._DELETE)
                    ):
                        break

                    if current.startswith("@@"):
                        raise ValueError(f"Add File '{path}' cannot contain hunks.")

                    if not current.startswith("+"):
                        raise ValueError(
                            f"Invalid Add File line in '{path}': "
                            f"{current!r}. "
                            "Every content line must start with '+'."
                        )

                    content_lines.append(current[1:])
                    i += 1

                content = self._join_added_lines(content_lines)

                operations.append(
                    PatchOperation(
                        operation="add",
                        path=path,
                        hunks=[],
                        content=content,
                    )
                )

                continue

            # DELETE
            if line.startswith(self._DELETE):
                path = line[len(self._DELETE) :].strip()

                if not path:
                    raise ValueError("Delete File path cannot be empty.")

                operations.append(
                    PatchOperation(
                        operation="delete",
                        path=path,
                        hunks=[],
                    )
                )

                i += 1
                continue

            raise ValueError(f"Unexpected patch line: {line!r}")

        return operations

    def _parse_hunks(
        self,
        lines: list[str],
        start_index: int,
    ) -> tuple[list[list[str]], int]:
        hunks: list[list[str]] = []

        current_hunk: list[str] | None = None
        i = start_index

        while i < len(lines) - 1:
            line = lines[i]

            # Next file operation starts.
            if (
                line.startswith(self._UPDATE)
                or line.startswith(self._ADD)
                or line.startswith(self._DELETE)
            ):
                break

            if line.startswith("@@"):
                if current_hunk is not None:
                    if not current_hunk:
                        raise ValueError("Empty patch hunk.")

                    hunks.append(current_hunk)

                current_hunk = []
                i += 1
                continue

            if current_hunk is None:
                raise ValueError("Update File content must begin with '@@'.")

            # A real empty line in a patch is represented by a
            # context prefix followed by nothing: " ".
            if line == "":
                raise ValueError(
                    "Invalid empty hunk line. "
                    "Use a leading space for an empty context line."
                )

            prefix = line[0]

            if prefix not in (" ", "+", "-"):
                raise ValueError(
                    f"Invalid hunk line: {line!r}. " "Expected ' ', '+' or '-'."
                )

            current_hunk.append(line)
            i += 1

        if current_hunk is not None:
            if not current_hunk:
                raise ValueError("Empty patch hunk.")

            hunks.append(current_hunk)

        return hunks, i

    # PLAN / VALIDATION
    def _build_plan(
        self,
        operations: list[PatchOperation],
    ) -> list[dict[str, Any]]:
        """
        Validate every operation and calculate all resulting contents
        BEFORE modifying the filesystem.

        This prevents a malformed second operation from causing the
        first operation to be written successfully and leaving the
        patch partially applied.
        """

        seen_paths: set[str] = set()
        plan: list[dict[str, Any]] = []

        for operation in operations:
            normalized_path = self._normalize_path(operation.path)

            if normalized_path in seen_paths:
                raise ValueError(f"Duplicate operation for path '{operation.path}'.")

            seen_paths.add(normalized_path)

            path = Path(normalized_path)

            if operation.operation == "add":
                plan.append(
                    self._plan_add(
                        path=path,
                        operation=operation,
                    )
                )

            elif operation.operation == "update":
                plan.append(
                    self._plan_update(
                        path=path,
                        operation=operation,
                    )
                )

            elif operation.operation == "delete":
                plan.append(
                    self._plan_delete(
                        path=path,
                    )
                )

            else:
                raise ValueError(
                    f"Unsupported patch operation " f"'{operation.operation}'."
                )

        return plan

    def _plan_add(
        self,
        path: Path,
        operation: PatchOperation,
    ) -> dict[str, Any]:
        if path.exists():
            raise ValueError(f"Cannot add '{path}': file already exists.")

        if path.is_dir():
            raise ValueError(f"Cannot add '{path}': path is a directory.")

        content = operation.content or ""

        return {
            "operation": "add",
            "path": path,
            "content": content,
            "added": self._count_lines(content),
            "removed": 0,
        }

    def _plan_update(
        self,
        path: Path,
        operation: PatchOperation,
    ) -> dict[str, Any]:
        if not path.exists():
            raise ValueError(f"Cannot update '{path}': file does not exist.")

        if not path.is_file():
            raise ValueError(f"Cannot update '{path}': path is not a file.")

        try:
            original = path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError(f"Cannot update non-UTF-8/binary file '{path}'.") from exc

        updated, added, removed = self._apply_hunks(
            original=original,
            hunks=operation.hunks,
            path=str(path),
        )

        return {
            "operation": "update",
            "path": path,
            "content": updated,
            "added": added,
            "removed": removed,
        }

    def _plan_delete(
        self,
        path: Path,
    ) -> dict[str, Any]:
        if not path.exists():
            raise ValueError(f"Cannot delete '{path}': file does not exist.")

        if not path.is_file():
            raise ValueError(f"Cannot delete '{path}': path is not a file.")

        return {
            "operation": "delete",
            "path": path,
            "content": None,
            "added": 0,
            "removed": 0,
        }

    # HUNK APPLICATION
    def _apply_hunks(
        self,
        original: str,
        hunks: list[list[str]],
        path: str,
    ) -> tuple[str, int, int]:
        """
        Apply all update hunks using exact matching.

        No fuzzy matching.
        No approximate matching.
        No guessing.

        A hunk must match exactly once.
        """

        newline = self._detect_newline(original)

        file_lines = original.splitlines(keepends=True)

        additions = 0
        removals = 0

        # Search position for the next hunk.
        search_from = 0

        for hunk_index, hunk in enumerate(
            hunks,
            start=1,
        ):
            old_lines: list[str] = []
            new_lines: list[str] = []

            for raw_line in hunk:
                prefix = raw_line[0]
                value = raw_line[1:]

                if prefix == " ":
                    old_lines.append(value)
                    new_lines.append(value)

                elif prefix == "-":
                    old_lines.append(value)

                elif prefix == "+":
                    new_lines.append(value)

                else:
                    raise ValueError(
                        f"Invalid hunk line in '{path}', "
                        f"hunk {hunk_index}: {raw_line!r}"
                    )

            if not old_lines:
                raise ValueError(
                    f"Hunk {hunk_index} in '{path}' "
                    "does not contain any context or removed lines."
                )

            old_normalized = [self._remove_newline(line) for line in old_lines]

            matches = self._find_matches(
                file_lines=file_lines,
                target=old_normalized,
            )

            # Prefer matches at/after the previous hunk.
            forward_matches = [
                position for position in matches if position >= search_from
            ]

            if not forward_matches:
                raise ValueError(
                    f"Patch context did not match in '{path}', " f"hunk {hunk_index}."
                )

            if len(forward_matches) > 1:
                raise ValueError(
                    f"Ambiguous patch in '{path}', "
                    f"hunk {hunk_index}: "
                    f"context matched {len(forward_matches)} times."
                )

            position = forward_matches[0]

            replacement = [
                self._format_new_line(
                    line=line,
                    newline=newline,
                )
                for line in new_lines
            ]

            file_lines[position : position + len(old_normalized)] = replacement

            search_from = position + len(replacement)

            additions += sum(1 for line in hunk if line.startswith("+"))

            removals += sum(1 for line in hunk if line.startswith("-"))

        return (
            "".join(file_lines),
            additions,
            removals,
        )

    def _find_matches(
        self,
        file_lines: list[str],
        target: list[str],
    ) -> list[int]:
        if not target:
            return []

        normalized_file = [self._remove_newline(line) for line in file_lines]

        matches: list[int] = []

        limit = len(normalized_file) - len(target) + 1

        if limit <= 0:
            return matches

        for position in range(limit):
            candidate = normalized_file[position : position + len(target)]

            if candidate == target:
                matches.append(position)

        return matches

    # FILESYSTEM
    def _apply_plan(
        self,
        plan: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """
        Apply a fully validated plan.

        Important:
            Validation is completed first, so patch syntax/context
            failures never cause partial modifications.
        """

        results: list[dict[str, Any]] = []

        for item in plan:
            path: Path = item["path"]
            operation = item["operation"]

            if operation == "add":
                path.parent.mkdir(
                    parents=True,
                    exist_ok=True,
                )

                path.write_text(
                    item["content"],
                    encoding="utf-8",
                )

                results.append(
                    {
                        "path": str(path),
                        "operation": "add",
                        "added": item["added"],
                        "removed": item["removed"],
                    }
                )

            elif operation == "update":
                path.write_text(
                    item["content"],
                    encoding="utf-8",
                )

                results.append(
                    {
                        "path": str(path),
                        "operation": "update",
                        "added": item["added"],
                        "removed": item["removed"],
                    }
                )

            elif operation == "delete":
                path.unlink()

                results.append(
                    {
                        "path": str(path),
                        "operation": "delete",
                        "added": 0,
                        "removed": 0,
                    }
                )

            else:
                raise RuntimeError(f"Unknown planned operation: {operation}")

        return results

    # HELPERS
    @staticmethod
    def _normalize_path(value: str) -> str:
        value = value.strip()

        if not value:
            raise ValueError("File path cannot be empty.")

        return str(Path(value))

    @staticmethod
    def _detect_newline(content: str) -> str:
        if "\r\n" in content:
            return "\r\n"

        return "\n"

    @staticmethod
    def _remove_newline(value: str) -> str:
        if value.endswith("\r\n"):
            return value[:-2]

        if value.endswith("\n"):
            return value[:-1]

        if value.endswith("\r"):
            return value[:-1]

        return value

    @staticmethod
    def _format_new_line(
        line: str,
        newline: str,
    ) -> str:
        return ApplyPatch._remove_newline(line) + newline

    @staticmethod
    def _join_added_lines(
        lines: list[str],
    ) -> str:
        if not lines:
            return ""

        return "\n".join(lines) + "\n"

    @staticmethod
    def _count_lines(
        content: str,
    ) -> int:
        if not content:
            return 0

        return len(content.splitlines())

    # TOOL RESULT CONTRACT
    def _success(
        self,
        *,
        summary: str,
        files: list[dict[str, Any]],
        statistics: dict[str, int],
    ) -> ToolResult:
        return ToolResult(
            success=True,
            name=self.name,
            content={
                "success": True,
                "operation": self.name,
                "summary": summary,
                "files": files,
                "statistics": statistics,
            },
            metadata={},
        )

    def _failure(
        self,
        *,
        error_type: str,
        message: str,
    ) -> ToolResult:
        return ToolResult(
            success=False,
            name=self.name,
            content={
                "success": False,
                "operation": self.name,
                "error": {
                    "type": error_type,
                    "message": message,
                },
            },
            metadata={},
        )

    def __repr__(self) -> str:
        return f"<Tool name='{self.name}'>"
