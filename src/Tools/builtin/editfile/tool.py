# src/Tools/builtin/editfile/tool.py

from pathlib import Path
from typing import Optional

from src.Tools.Tool import Tool
from src.Tools.ToolResult import ToolResult


class EditFile(Tool):

    name = "Edit"

    description = (
        "Edit a file by replacing exact content within an optional line range."
    )

    parameters = {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "Path to the file to edit",
            },
            "old_content": {
                "type": "string",
                "description": "Exact content to search for",
            },
            "new_content": {
                "type": "string",
                "description": "Content to replace it with",
            },
            "chunk_start": {
                "type": "integer",
                "description": (
                    "Optional start line number, 1-indexed. "
                    "If omitted, starts from the beginning."
                ),
            },
            "chunk_end": {
                "type": "integer",
                "description": (
                    "Optional end line number, 1-indexed. "
                    "If omitted, continues to the end."
                ),
            },
        },
        "required": [
            "file_path",
            "old_content",
            "new_content",
        ],
    }

    def execute(
        self,
        file_path: str,
        old_content: str,
        new_content: str,
        chunk_start: Optional[int] = None,
        chunk_end: Optional[int] = None,
    ) -> ToolResult:

        if not file_path:
            return ToolResult(
                success=False,
                content="Path cannot be empty",
            )

        if not old_content:
            return ToolResult(
                success=False,
                content="Old content cannot be empty",
            )

        path = Path(file_path)

        if not path.exists():
            return ToolResult(
                success=False,
                content=f"File not found: {file_path}",
            )

        if not path.is_file():
            return ToolResult(
                success=False,
                content=f"Path is not a file: {file_path}",
            )

        try:
            with open(path, "r", encoding="utf-8") as f:
                lines = f.readlines()

            total_lines = len(lines)

            start_line = chunk_start or 1
            end_line = chunk_end or total_lines

            if start_line < 1:
                return ToolResult(
                    success=False,
                    content=f"chunk_start must be >= 1 (got {start_line})",
                )

            if end_line < 1:
                return ToolResult(
                    success=False,
                    content=f"chunk_end must be >= 1 (got {end_line})",
                )

            if start_line > total_lines:
                return ToolResult(
                    success=False,
                    content=(
                        f"chunk_start ({start_line}) is beyond the end "
                        f"of the file ({total_lines} lines)"
                    ),
                )

            if start_line > end_line:
                return ToolResult(
                    success=False,
                    content=(
                        f"chunk_start ({start_line}) must be less than "
                        f"or equal to chunk_end ({end_line})"
                    ),
                )

            end_line = min(end_line, total_lines)

            start_idx = start_line - 1
            end_idx = end_line

            target = "".join(lines[start_idx:end_idx])

            match_count = target.count(old_content)

            if match_count == 0:
                return ToolResult(
                    success=False,
                    content=(
                        f'Content not found in lines '
                        f'{start_line}-{end_line}: "{old_content}"'
                    ),
                    metadata={
                        "total_lines": total_lines,
                        "start_line": start_line,
                        "end_line": end_line,
                        "matches": 0,
                        "modified": False,
                    },
                )

            if match_count > 1:
                return ToolResult(
                    success=False,
                    content=(
                        f"Ambiguous edit: old_content matched "
                        f"{match_count} times in lines "
                        f"{start_line}-{end_line}."
                    ),
                    metadata={
                        "total_lines": total_lines,
                        "start_line": start_line,
                        "end_line": end_line,
                        "matches": match_count,
                        "modified": False,
                    },
                )

            modified_target = target.replace(
                old_content,
                new_content,
                1,
            )

            new_lines = (
                lines[:start_idx]
                + [modified_target]
                + lines[end_idx:]
            )

            with open(path, "w", encoding="utf-8") as f:
                f.writelines(new_lines)

            return ToolResult(
                success=True,
                content=f"Successfully edited {file_path}",
                metadata={
                    "total_lines_before": total_lines,
                    "start_line": start_line,
                    "end_line": end_line,
                    "matches": match_count,
                    "modified": True,
                    "old_content": old_content,
                    "new_content": new_content,
                },
            )

        except UnicodeDecodeError:
            return ToolResult(
                success=False,
                content=f"Cannot read binary file: {file_path}",
            )

        except PermissionError:
            return ToolResult(
                success=False,
                content=f"Permission denied: {file_path}",
            )

        except Exception as e:
            return ToolResult(
                success=False,
                content=f"Error editing file: {e}",
            )

    def __repr__(self) -> str:
        return f"<Tool name='{self.name}'>"

