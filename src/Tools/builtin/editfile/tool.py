from pathlib import Path
from typing import Optional

from src.Tools.Tool import Tool
from src.Tools.ToolResult import ToolResult


class EditFile(Tool):
    name = "Edit"

    description = (
        "Edit an existing text file. "
        "If old_content is provided, replace exactly one occurrence "
        "within the optional line range. "
        "If old_content is omitted, rewrite the entire file with new_content. "
        "Use exact content matching for targeted edits."
    )

    parameters = {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "Path to the file to edit.",
            },
            "old_content": {
                "type": "string",
                "description": (
                    "Optional exact content to replace. "
                    "If omitted, the entire file is rewritten "
                    "using new_content."
                ),
            },
            "new_content": {
                "type": "string",
                "description": (
                    "Replacement content. "
                    "When old_content is omitted, this becomes "
                    "the complete new file content."
                ),
            },
            "chunk_start": {
                "type": "integer",
                "description": (
                    "Optional start line number, 1-indexed. "
                    "Used for targeted replacement."
                ),
            },
            "chunk_end": {
                "type": "integer",
                "description": (
                    "Optional end line number, 1-indexed. "
                    "Used for targeted replacement."
                ),
            },
        },
        "required": [
            "file_path",
            "new_content",
        ],
    }

    def execute(
        self,
        file_path: str,
        new_content: str,
        old_content: Optional[str] = None,
        chunk_start: Optional[int] = None,
        chunk_end: Optional[int] = None,
    ) -> ToolResult:

        if not file_path:
            return ToolResult(
                success=False,
                content="Path cannot be empty.",
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

        if new_content is None:
            return ToolResult(
                success=False,
                content="new_content cannot be null.",
            )

        try:
            with open(
                path,
                "r",
                encoding="utf-8",
            ) as f:
                lines = f.readlines()

            total_lines = len(lines)

            # -------------------------------------------------
            # Full-file rewrite mode
            # -------------------------------------------------

            if old_content is None or old_content == "":

                with open(
                    path,
                    "w",
                    encoding="utf-8",
                ) as f:
                    f.write(new_content)

                return ToolResult(
                    success=True,
                    content=(f"Successfully rewrote {file_path}."),
                    metadata={
                        "total_lines_before": total_lines,
                        "modified": True,
                        "mode": "rewrite",
                    },
                )

            # -------------------------------------------------
            # Targeted replacement mode
            # -------------------------------------------------

            start_line = chunk_start or 1
            end_line = chunk_end or total_lines

            if start_line < 1:

                return ToolResult(
                    success=False,
                    content=(f"chunk_start must be >= 1 " f"(got {start_line})."),
                )

            if end_line < 1:

                return ToolResult(
                    success=False,
                    content=(f"chunk_end must be >= 1 " f"(got {end_line})."),
                )

            if start_line > total_lines:

                return ToolResult(
                    success=False,
                    content=(
                        f"chunk_start ({start_line}) is beyond "
                        f"the end of the file "
                        f"({total_lines} lines)."
                    ),
                )

            if start_line > end_line:

                return ToolResult(
                    success=False,
                    content=(
                        f"chunk_start ({start_line}) must be "
                        f"less than or equal to "
                        f"chunk_end ({end_line})."
                    ),
                )

            end_line = min(
                end_line,
                total_lines,
            )

            start_idx = start_line - 1
            end_idx = end_line

            target = "".join(lines[start_idx:end_idx])

            match_count = target.count(old_content)

            if match_count == 0:

                return ToolResult(
                    success=False,
                    content=(
                        "Content not found in the specified "
                        "line range. Read the relevant range "
                        "and retry with the exact content, "
                        "or omit old_content to rewrite the file."
                    ),
                    metadata={
                        "total_lines": total_lines,
                        "start_line": start_line,
                        "end_line": end_line,
                        "matches": 0,
                        "modified": False,
                        "mode": "replace",
                    },
                )

            if match_count > 1:

                return ToolResult(
                    success=False,
                    content=(
                        f"Ambiguous edit: old_content matched "
                        f"{match_count} times in lines "
                        f"{start_line}-{end_line}. "
                        "Provide a more specific old_content "
                        "or use a smaller line range."
                    ),
                    metadata={
                        "total_lines": total_lines,
                        "start_line": start_line,
                        "end_line": end_line,
                        "matches": match_count,
                        "modified": False,
                        "mode": "replace",
                    },
                )

            modified_target = target.replace(
                old_content,
                new_content,
                1,
            )

            new_lines = lines[:start_idx] + [modified_target] + lines[end_idx:]

            with open(
                path,
                "w",
                encoding="utf-8",
            ) as f:
                f.writelines(new_lines)

            return ToolResult(
                success=True,
                content=(f"Successfully edited {file_path}."),
                metadata={
                    "total_lines_before": total_lines,
                    "start_line": start_line,
                    "end_line": end_line,
                    "matches": match_count,
                    "modified": True,
                    "mode": "replace",
                },
            )

        except UnicodeDecodeError:

            return ToolResult(
                success=False,
                content=(f"Cannot read binary file: " f"{file_path}"),
            )

        except PermissionError:

            return ToolResult(
                success=False,
                content=(f"Permission denied: " f"{file_path}"),
            )

        except Exception as e:

            return ToolResult(
                success=False,
                content=(f"Error editing file: {e}"),
            )

    def __repr__(self) -> str:
        return f"<Tool name='{self.name}'>"
