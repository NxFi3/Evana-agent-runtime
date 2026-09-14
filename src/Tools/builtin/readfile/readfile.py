from pathlib import Path
from typing import Optional

from src.Tools.Tool import Tool
from src.Tools.ToolResult import ToolResult


class ReadFile(Tool):

    name = "Read"

    MAX_OUTPUT_CHARS = 4000

    description = (
        "Read a file or list a directory.\n"
        "For files, use start_line/end_line to inspect a specific range.\n"
        "Large file reads are bounded to keep agent context small.\n"
        "For directories, provide only file_path."
    )

    parameters = {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "Path of the file or directory to read.",
            },
            "start_line": {
                "type": "integer",
                "description": "First line to read. Optional.",
            },
            "end_line": {
                "type": "integer",
                "description": "Last line to read. Optional.",
            },
        },
        "required": ["file_path"],
    }

    @classmethod
    def _bounded_content(
        cls,
        content: str
    ) -> tuple[str, bool]:

        content = content or ""

        if len(content) <= cls.MAX_OUTPUT_CHARS:
            return content, False

        head = int(
            cls.MAX_OUTPUT_CHARS * 0.75
        )

        tail = (
            cls.MAX_OUTPUT_CHARS
            - head
        )

        omitted = (
            len(content)
            - head
            - tail
        )

        bounded = (
            content[:head].rstrip()
            + "\n\n"
            + f"... {omitted} characters omitted; "
              "read a narrower line range ...\n\n"
            + content[-tail:].lstrip()
        )

        return bounded, True

    def execute(
        self,
        file_path: str,
        start_line: Optional[int] = None,
        end_line: Optional[int] = None
    ) -> ToolResult:

        if not file_path:
            return ToolResult(
                success=False,
                content="Path cannot be empty"
            )

        try:

            path = Path(file_path)

            # -------------------------
            # File
            # -------------------------
            if path.is_file():

                with open(
                    path,
                    "r",
                    encoding="utf-8"
                ) as f:
                    lines = f.readlines()

                total_lines = len(lines)

                if start_line is not None:
                    if start_line < 1:
                        return ToolResult(
                            success=False,
                            content=(
                                "start_line must be >= 1 "
                                f"(got {start_line})"
                            )
                        )

                    if start_line > total_lines:
                        return ToolResult(
                            success=False,
                            content=(
                                f"start_line ({start_line}) is beyond "
                                f"the end of the file "
                                f"({total_lines} lines)"
                            )
                        )

                if end_line is not None:
                    if end_line < 1:
                        return ToolResult(
                            success=False,
                            content=(
                                "end_line must be >= 1 "
                                f"(got {end_line})"
                            )
                        )

                if (
                    start_line is not None
                    and end_line is not None
                    and start_line > end_line
                ):
                    return ToolResult(
                        success=False,
                        content=(
                            f"start_line ({start_line}) must be "
                            f"less than or equal to "
                            f"end_line ({end_line})"
                        )
                    )

                start_idx = (
                    0
                    if start_line is None
                    else start_line - 1
                )

                end_idx = (
                    total_lines
                    if end_line is None
                    else min(end_line, total_lines)
                )

                content = "".join(
                    lines[start_idx:end_idx]
                )

                bounded_content, truncated = (
                    self._bounded_content(content)
                )

                suffix = ""

                if truncated:
                    suffix = (
                        "\n\n"
                        "Output was truncated. "
                        "Use start_line/end_line to inspect "
                        "the required section."
                    )

                final_content = (
                    bounded_content
                    + suffix
                )

                return ToolResult(
                    success=True,
                    content=final_content,
                    metadata={
                        "total_lines": total_lines,
                        "start_line": start_idx + 1,
                        "end_line": end_idx,
                        "lines_returned": end_idx - start_idx,
                        "truncated": truncated,
                        "output_limit_chars": (
                            self.MAX_OUTPUT_CHARS
                        ),
                    }
                )

            # -------------------------
            # Directory
            # -------------------------
            if path.is_dir():

                items = sorted(
                    path.iterdir(),
                    key=lambda item: item.name.lower()
                )

                if not items:
                    return ToolResult(
                        success=True,
                        content="Directory is empty.",
                        metadata={
                            "total_files": 0
                        }
                    )

                names = [
                    item.name
                    for item in items
                ]

                content = (
                    f"Contents of {path.name}:\n"
                    + "\n".join(names)
                )

                bounded_content, truncated = (
                    self._bounded_content(content)
                )

                if truncated:
                    bounded_content += (
                        "\n\n"
                        "Directory listing truncated."
                    )

                return ToolResult(
                    success=True,
                    content=bounded_content,
                    metadata={
                        "total_files": len(items),
                        "truncated": truncated,
                    }
                )

            return ToolResult(
                success=False,
                content="Nothing Found."
            )

        except UnicodeDecodeError:

            return ToolResult(
                success=False,
                content=(
                    f"Cannot read binary file: {file_path}"
                )
            )

        except PermissionError:

            return ToolResult(
                success=False,
                content=(
                    f"Permission denied: {file_path}"
                )
            )

        except Exception as e:

            return ToolResult(
                success=False,
                content=f"Error reading {file_path}: {e}"
            )

    def __repr__(self) -> str:
        return f"<Tool name='{self.name}'>"