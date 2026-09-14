import subprocess
import time
from pathlib import Path
from typing import Optional
import re

from src.Tools.Tool import Tool
from src.Tools.ToolResult import ToolResult


class Shell(Tool):

    name = "Shell"

    MAX_OUTPUT_CHARS = 2400

    description = (
        "Execute a shell command and return a compact bounded "
        "stdout/stderr result, exit code, and execution duration."
    )

    parameters = {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "Shell command to execute.",
            },
            "cwd": {
                "type": "string",
                "description": (
                    "Optional working directory for the command. "
                    "If omitted, uses the current working directory."
                ),
            },
            "timeout": {
                "type": "integer",
                "description": (
                    "Maximum execution time in seconds. "
                    "If omitted, uses 120 seconds."
                ),
                "default": 120,
            },
            "confirm": {
                "type": "string",
                "enum": ["Y", "N"],
                "description": (
                    "Set to Y to execute the command. "
                    "Set to N to cancel execution."
                ),
                "default": "Y",
            },
        },
        "required": ["command"],
    }


    @classmethod
    def _bounded_output(
        cls,
        value: str
    ) -> tuple[str, bool]:

        value = str(
            value or ""
        ).strip()


        if len(value) <= cls.MAX_OUTPUT_CHARS:

            return value, False


        # Keep slightly more of the beginning because
        # commands often put important setup/context there.
        head = int(
            cls.MAX_OUTPUT_CHARS * 0.60
        )

        tail = (
            cls.MAX_OUTPUT_CHARS
            - head
        )


        return (
            value[:head].rstrip()
            + "\n\n"
            + "... OUTPUT TRUNCATED ...\n\n"
            + value[-tail:].lstrip(),
            True,
        )


    def execute(
        self,
        command: str,
        cwd: Optional[str] = None,
        timeout: int = 120,
        confirm: str = "Y",
    ) -> ToolResult:

        BLOCKED_PATTERNS = [
            r"rm\s+-rf\s+/",
            r":\(\)\{.*\};:",
            r"mkfs\.",
            r"dd\s+if=.*of=/dev/",
        ]


        for pattern in BLOCKED_PATTERNS:

            if re.search(
                pattern,
                command or ""
            ):

                return ToolResult(
                    success=False,
                    content=(
                        "Command blocked for safety."
                    )
                )


        if not command or not command.strip():

            return ToolResult(
                success=False,
                content="Command cannot be empty."
            )


        confirm = str(
            confirm
        ).strip().upper()


        if confirm not in ("Y", "N"):

            return ToolResult(
                success=False,
                content=(
                    "Invalid confirmation. Use Y or N."
                )
            )


        if confirm != "Y":

            return ToolResult(
                success=False,
                content=(
                    "Command execution cancelled. "
                    "Confirmation Y is required."
                ),
                metadata={
                    "command": command,
                    "executed": False,
                    "confirmed": False,
                },
            )


        if timeout is None:

            timeout = 120


        if not isinstance(
            timeout,
            int
        ) or timeout <= 0:

            return ToolResult(
                success=False,
                content=(
                    "Timeout must be a positive integer."
                )
            )


        working_directory = None


        if cwd:

            working_directory = Path(
                cwd
            )


            if not working_directory.exists():

                return ToolResult(
                    success=False,
                    content=(
                        f"Working directory not found: "
                        f"{cwd}"
                    )
                )


            if not working_directory.is_dir():

                return ToolResult(
                    success=False,
                    content=(
                        f"Working directory is not a directory: "
                        f"{cwd}"
                    )
                )


        start_time = time.perf_counter()


        try:

            process = subprocess.run(
                command,
                shell=True,
                cwd=(
                    str(working_directory)
                    if working_directory
                    else None
                ),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
            )


            duration = (
                time.perf_counter()
                - start_time
            )


            stdout = process.stdout or ""
            stderr = process.stderr or ""


            bounded_stdout, stdout_truncated = (
                self._bounded_output(stdout)
            )

            bounded_stderr, stderr_truncated = (
                self._bounded_output(stderr)
            )


            success = (
                process.returncode == 0
            )


            output_parts = []


            if bounded_stdout:

                output_parts.append(
                    f"STDOUT:\n{bounded_stdout}"
                )


            if bounded_stderr:

                output_parts.append(
                    f"STDERR:\n{bounded_stderr}"
                )


            if not output_parts:

                output_parts.append(
                    "Command completed with no output."
                )


            output_parts.append(
                f"Exit code: {process.returncode}"
            )


            if stdout_truncated or stderr_truncated:

                output_parts.append(
                    "Output truncated for agent context."
                )


            return ToolResult(
                success=success,
                content="\n\n".join(
                    output_parts
                ),
                metadata={
                    # Full output remains available outside
                    # the compact context representation.
                    "command": command,
                    "cwd": (
                        str(working_directory)
                        if working_directory
                        else None
                    ),
                    "timeout": timeout,
                    "exit_code": process.returncode,
                    "stdout": stdout,
                    "stderr": stderr,
                    "stdout_truncated": stdout_truncated,
                    "stderr_truncated": stderr_truncated,
                    "output_limit_chars": (
                        self.MAX_OUTPUT_CHARS
                    ),
                    "duration": duration,
                    "executed": True,
                    "confirmed": True,
                },
            )


        except subprocess.TimeoutExpired as e:

            duration = (
                time.perf_counter()
                - start_time
            )


            stdout = e.stdout or ""
            stderr = e.stderr or ""


            if isinstance(
                stdout,
                bytes
            ):

                stdout = stdout.decode(
                    "utf-8",
                    errors="replace"
                )


            if isinstance(
                stderr,
                bytes
            ):

                stderr = stderr.decode(
                    "utf-8",
                    errors="replace"
                )


            bounded_stdout, stdout_truncated = (
                self._bounded_output(stdout)
            )

            bounded_stderr, stderr_truncated = (
                self._bounded_output(stderr)
            )


            output = (
                f"Command timed out after "
                f"{timeout} seconds."
            )


            if bounded_stdout:

                output += (
                    f"\n\nSTDOUT:\n"
                    f"{bounded_stdout}"
                )


            if bounded_stderr:

                output += (
                    f"\n\nSTDERR:\n"
                    f"{bounded_stderr}"
                )


            return ToolResult(
                success=False,
                content=output,
                metadata={
                    "command": command,
                    "cwd": (
                        str(working_directory)
                        if working_directory
                        else None
                    ),
                    "timeout": timeout,
                    "exit_code": None,
                    "stdout": stdout,
                    "stderr": stderr,
                    "stdout_truncated": stdout_truncated,
                    "stderr_truncated": stderr_truncated,
                    "output_limit_chars": (
                        self.MAX_OUTPUT_CHARS
                    ),
                    "duration": duration,
                    "executed": True,
                    "confirmed": True,
                    "timed_out": True,
                },
            )


        except FileNotFoundError as e:

            duration = (
                time.perf_counter()
                - start_time
            )

            return ToolResult(
                success=False,
                content=(
                    f"Command execution failed: {e}"
                ),
                metadata={
                    "command": command,
                    "cwd": (
                        str(working_directory)
                        if working_directory
                        else None
                    ),
                    "timeout": timeout,
                    "exit_code": None,
                    "duration": duration,
                    "executed": False,
                    "confirmed": True,
                },
            )


        except PermissionError:

            duration = (
                time.perf_counter()
                - start_time
            )

            return ToolResult(
                success=False,
                content=(
                    "Permission denied while "
                    "executing command."
                ),
                metadata={
                    "command": command,
                    "cwd": (
                        str(working_directory)
                        if working_directory
                        else None
                    ),
                    "timeout": timeout,
                    "exit_code": None,
                    "duration": duration,
                    "executed": False,
                    "confirmed": True,
                },
            )


        except Exception as e:

            duration = (
                time.perf_counter()
                - start_time
            )

            return ToolResult(
                success=False,
                content=(
                    f"Shell execution error: {e}"
                ),
                metadata={
                    "command": command,
                    "cwd": (
                        str(working_directory)
                        if working_directory
                        else None
                    ),
                    "timeout": timeout,
                    "exit_code": None,
                    "duration": duration,
                    "executed": False,
                    "confirmed": True,
                },
            )


    def __repr__(self) -> str:

        return "<Tool name='Shell'>"