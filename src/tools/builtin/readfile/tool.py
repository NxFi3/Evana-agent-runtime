from __future__ import annotations

from pathlib import Path
from typing import Any

from src.tools.Tool import Tool
from src.models.ToolResult import ToolResult


class ReadFile(Tool):
    """
    Read files or list directories for the Evana agent runtime.

    The result is returned through ToolResult.content as a structured,
    JSON-compatible dictionary so it can be inserted directly into
    the agent context.
    """

    name = "read_file"

    DEFAULT_MAX_OUTPUT_CHARS = 8_000
    MAX_OUTPUT_CHARS = 32_000
    MIN_OUTPUT_CHARS = 512

    description = (
        "Read a text file or list a directory. "
        "For files, optional start_line and end_line can limit the returned "
        "range. Output is bounded to protect agent context."
    )

    parameters = {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": ("Path to the file or directory to read."),
            },
            "start_line": {
                "type": "integer",
                "description": (
                    "Optional 1-based first line to return. "
                    "If omitted, starts from the beginning."
                ),
                "minimum": 1,
            },
            "end_line": {
                "type": "integer",
                "description": (
                    "Optional 1-based last line to return. "
                    "If omitted, reads through the end of the file."
                ),
                "minimum": 1,
            },
            "max_output_chars": {
                "type": "integer",
                "description": (
                    "Maximum number of characters returned in content. "
                    f"Default: {DEFAULT_MAX_OUTPUT_CHARS}."
                ),
                "default": DEFAULT_MAX_OUTPUT_CHARS,
                "minimum": MIN_OUTPUT_CHARS,
                "maximum": MAX_OUTPUT_CHARS,
            },
        },
        "required": ["file_path"],
        "additionalProperties": False,
    }

    # PUBLIC API
    def execute(
        self,
        file_path: str,
        start_line: int | None = None,
        end_line: int | None = None,
        max_output_chars: int = DEFAULT_MAX_OUTPUT_CHARS,
    ) -> ToolResult:
        """
        ToolManager invokes this as:

            tool.execute(**toolcall.args)
        """

        validation_error = self._validate_arguments(
            file_path=file_path,
            start_line=start_line,
            end_line=end_line,
            max_output_chars=max_output_chars,
        )

        if validation_error is not None:
            return validation_error

        path = Path(file_path).expanduser()

        try:
            path = path.resolve()
        except OSError as exc:
            return self._error(
                error_type="path_error",
                message=f"Could not resolve path: {exc}",
            )

        if path.is_file():
            return self._read_file(
                path=path,
                start_line=start_line,
                end_line=end_line,
                max_output_chars=max_output_chars,
            )

        if path.is_dir():
            return self._read_directory(
                path=path,
                max_output_chars=max_output_chars,
            )

        return self._error(
            error_type="not_found",
            message=f"File or directory not found: {file_path}",
        )

    # VALIDATION
    def _validate_arguments(
        self,
        *,
        file_path: Any,
        start_line: Any,
        end_line: Any,
        max_output_chars: Any,
    ) -> ToolResult | None:

        if not isinstance(file_path, str):
            return self._error(
                error_type="invalid_argument",
                message="file_path must be a string.",
            )

        if not file_path.strip():
            return self._error(
                error_type="invalid_argument",
                message="file_path cannot be empty.",
            )

        if start_line is not None:
            if not isinstance(start_line, int):
                return self._error(
                    error_type="invalid_argument",
                    message="start_line must be an integer.",
                )

            if start_line < 1:
                return self._error(
                    error_type="invalid_argument",
                    message="start_line must be >= 1.",
                )

        if end_line is not None:
            if not isinstance(end_line, int):
                return self._error(
                    error_type="invalid_argument",
                    message="end_line must be an integer.",
                )

            if end_line < 1:
                return self._error(
                    error_type="invalid_argument",
                    message="end_line must be >= 1.",
                )

        if start_line is not None and end_line is not None and start_line > end_line:
            return self._error(
                error_type="invalid_argument",
                message=("start_line must be less than or equal to end_line."),
            )

        if not isinstance(max_output_chars, int):
            return self._error(
                error_type="invalid_argument",
                message="max_output_chars must be an integer.",
            )

        if not (self.MIN_OUTPUT_CHARS <= max_output_chars <= self.MAX_OUTPUT_CHARS):
            return self._error(
                error_type="invalid_argument",
                message=(
                    "max_output_chars must be between "
                    f"{self.MIN_OUTPUT_CHARS} and "
                    f"{self.MAX_OUTPUT_CHARS}."
                ),
            )

        return None

    # FILE
    def _read_file(
        self,
        *,
        path: Path,
        start_line: int | None,
        end_line: int | None,
        max_output_chars: int,
    ) -> ToolResult:

        try:
            with open(
                path,
                "r",
                encoding="utf-8",
                errors="strict",
            ) as file:
                lines = file.readlines()

        except UnicodeDecodeError:
            return self._error(
                error_type="binary_or_non_utf8",
                message=f"Cannot read non-UTF-8/binary file: {path}",
                extra={
                    "path": str(path),
                    "type": "file",
                },
            )

        except PermissionError:
            return self._error(
                error_type="permission_error",
                message=f"Permission denied: {path}",
                extra={
                    "path": str(path),
                    "type": "file",
                },
            )

        except OSError as exc:
            return self._error(
                error_type="read_error",
                message=f"Could not read '{path}': {exc}",
                extra={
                    "path": str(path),
                    "type": "file",
                },
            )

        total_lines = len(lines)

        # Empty file
        if total_lines == 0:
            return ToolResult(
                success=True,
                name=self.name,
                content={
                    "success": True,
                    "type": "file",
                    "path": str(path),
                    "content": "",
                    "start_line": None,
                    "end_line": None,
                    "lines_returned": 0,
                    "total_lines": 0,
                    "truncated": False,
                },
                metadata={},
            )

        # Resolve requested range
        actual_start = 1 if start_line is None else start_line

        actual_end = total_lines if end_line is None else end_line

        if actual_start > total_lines:
            return self._error(
                error_type="line_out_of_range",
                message=(
                    f"start_line ({actual_start}) is beyond the end "
                    f"of the file ({total_lines} lines)."
                ),
                extra={
                    "path": str(path),
                    "type": "file",
                    "total_lines": total_lines,
                },
            )

        actual_end = min(
            actual_end,
            total_lines,
        )

        start_index = actual_start - 1
        end_index = actual_end

        selected_lines = lines[start_index:end_index]

        raw_content = "".join(selected_lines)

        # Bound content

        bounded_content, truncated = self._truncate(
            raw_content,
            max_output_chars,
        )

        # Count actual lines represented in returned content.
        if truncated:
            lines_returned = self._estimate_visible_lines(bounded_content)
        else:
            lines_returned = len(selected_lines)

        return ToolResult(
            success=True,
            name=self.name,
            content={
                "success": True,
                "type": "file",
                "path": str(path),
                "content": bounded_content,
                "start_line": actual_start,
                "end_line": actual_end,
                "lines_requested": actual_end - actual_start + 1,
                "lines_returned": lines_returned,
                "total_lines": total_lines,
                "truncated": truncated,
                "max_output_chars": max_output_chars,
            },
            metadata={},
        )

    # DIRECTORY
    def _read_directory(
        self,
        *,
        path: Path,
        max_output_chars: int,
    ) -> ToolResult:

        try:
            entries = sorted(
                path.iterdir(),
                key=lambda item: (
                    not item.is_dir(),
                    item.name.lower(),
                ),
            )
        except PermissionError:
            return self._error(
                error_type="permission_error",
                message=f"Permission denied: {path}",
                extra={
                    "path": str(path),
                    "type": "directory",
                },
            )
        except OSError as exc:
            return self._error(
                error_type="read_error",
                message=f"Could not read directory '{path}': {exc}",
                extra={
                    "path": str(path),
                    "type": "directory",
                },
            )

        items: list[dict[str, str]] = []

        for entry in entries:
            items.append(
                {
                    "name": entry.name,
                    "type": (
                        "directory"
                        if entry.is_dir()
                        else "file" if entry.is_file() else "other"
                    ),
                }
            )

        # Build bounded listing
        visible_items: list[dict[str, str]] = []
        used_chars = 0
        truncated = False

        for item in items:
            line = f"{item['type']}: {item['name']}"

            # +1 accounts for newline.
            required = len(line) + 1

            if used_chars + required > max_output_chars:
                truncated = True
                break

            visible_items.append(item)
            used_chars += required

        listing = "\n".join(f"{item['type']}: {item['name']}" for item in visible_items)

        if truncated:
            remaining = len(items) - len(visible_items)

            marker = f"\n\n... {remaining} item(s) omitted ..."

            listing, _ = self._truncate(
                listing + marker,
                max_output_chars,
            )

        return ToolResult(
            success=True,
            name=self.name,
            content={
                "success": True,
                "type": "directory",
                "path": str(path),
                "content": listing,
                "total_entries": len(entries),
                "entries_returned": len(visible_items),
                "truncated": truncated,
                "max_output_chars": max_output_chars,
            },
            metadata={},
        )

    # OUTPUT
    @staticmethod
    def _truncate(
        value: str,
        limit: int,
    ) -> tuple[str, bool]:

        value = value or ""

        if len(value) <= limit:
            return value, False

        head = int(limit * 0.70)

        tail = limit - head

        omitted = len(value) - head - tail

        bounded = (
            value[:head].rstrip() + "\n\n" + f"... {omitted} characters omitted; "
            "use start_line/end_line to inspect a narrower range ...\n\n"
            + value[-tail:].lstrip()
        )

        return bounded, True

    @staticmethod
    def _estimate_visible_lines(
        content: str,
    ) -> int:
        if not content:
            return 0

        return len(content.splitlines())

    # RESULTS
    def _error(
        self,
        *,
        error_type: str,
        message: str,
        extra: dict[str, Any] | None = None,
    ) -> ToolResult:

        content: dict[str, Any] = {
            "success": False,
            "error": {
                "type": error_type,
                "message": message,
            },
        }

        if extra:
            content.update(extra)

        return ToolResult(
            success=False,
            name=self.name,
            content=content,
            metadata={},
        )

    def __repr__(self) -> str:
        return "<Tool name='read_file'>"
