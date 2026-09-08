# src/Tools/builtin/shell/shell.py

import subprocess
import time
from pathlib import Path
from typing import Optional

from src.Tools.Tool import Tool
from src.Tools.ToolResult import ToolResult


class Shell(Tool):

    name = "Shell"

    description = (
        "Execute a shell command and return its stdout, stderr, "
        "exit code, and execution duration."
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
                "default": "N",
            },
        },
        "required": ["command"],
    }

    def execute(
        self,
        command: str,
        cwd: Optional[str] = None,
        timeout: int = 120,
        confirm: str = "N",
    ) -> ToolResult:

        if not command or not command.strip():
            return ToolResult(
                success=False,
                content="Command cannot be empty.",
            )

        confirm = str(confirm).strip().upper()

        if confirm not in ("Y", "N"):
            return ToolResult(
                success=False,
                content="Invalid confirmation. Use Y or N.",
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

        if not isinstance(timeout, int) or timeout <= 0:
            return ToolResult(
                success=False,
                content="Timeout must be a positive integer.",
            )

        working_directory = None

        if cwd:
            working_directory = Path(cwd)

            if not working_directory.exists():
                return ToolResult(
                    success=False,
                    content=f"Working directory not found: {cwd}",
                )

            if not working_directory.is_dir():
                return ToolResult(
                    success=False,
                    content=f"Working directory is not a directory: {cwd}",
                )

        start_time = time.perf_counter()

        try:
            process = subprocess.run(
                command,
                shell=True,
                cwd=str(working_directory) if working_directory else None,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
            )

            duration = time.perf_counter() - start_time

            stdout = process.stdout or ""
            stderr = process.stderr or ""

            success = process.returncode == 0

            output_parts = []

            if stdout:
                output_parts.append(
                    f"STDOUT:\n{stdout.rstrip()}"
                )

            if stderr:
                output_parts.append(
                    f"STDERR:\n{stderr.rstrip()}"
                )

            if not output_parts:
                output_parts.append(
                    "Command completed with no output."
                )

            output_parts.append(
                f"Exit code: {process.returncode}"
            )

            return ToolResult(
                success=success,
                content="\n\n".join(output_parts),
                metadata={
                    "command": command,
                    "cwd": str(working_directory)
                    if working_directory
                    else None,
                    "timeout": timeout,
                    "exit_code": process.returncode,
                    "stdout": stdout,
                    "stderr": stderr,
                    "duration": duration,
                    "executed": True,
                    "confirmed": True,
                },
            )

        except subprocess.TimeoutExpired as e:
            duration = time.perf_counter() - start_time

            stdout = e.stdout or ""
            stderr = e.stderr or ""

            if isinstance(stdout, bytes):
                stdout = stdout.decode(
                    "utf-8",
                    errors="replace",
                )

            if isinstance(stderr, bytes):
                stderr = stderr.decode(
                    "utf-8",
                    errors="replace",
                )

            return ToolResult(
                success=False,
                content=(
                    f"Command timed out after {timeout} seconds.\n\n"
                    f"STDOUT:\n{stdout}\n\n"
                    f"STDERR:\n{stderr}"
                ),
                metadata={
                    "command": command,
                    "cwd": str(working_directory)
                    if working_directory
                    else None,
                    "timeout": timeout,
                    "exit_code": None,
                    "stdout": stdout,
                    "stderr": stderr,
                    "duration": duration,
                    "executed": True,
                    "confirmed": True,
                    "timeout": True,
                },
            )

        except FileNotFoundError as e:
            duration = time.perf_counter() - start_time

            return ToolResult(
                success=False,
                content=f"Command execution failed: {e}",
                metadata={
                    "command": command,
                    "cwd": str(working_directory)
                    if working_directory
                    else None,
                    "timeout": timeout,
                    "exit_code": None,
                    "duration": duration,
                    "executed": False,
                    "confirmed": True,
                },
            )

        except PermissionError:
            duration = time.perf_counter() - start_time

            return ToolResult(
                success=False,
                content="Permission denied while executing command.",
                metadata={
                    "command": command,
                    "cwd": str(working_directory)
                    if working_directory
                    else None,
                    "timeout": timeout,
                    "exit_code": None,
                    "duration": duration,
                    "executed": False,
                    "confirmed": True,
                },
            )

        except Exception as e:
            duration = time.perf_counter() - start_time

            return ToolResult(
                success=False,
                content=f"Shell execution error: {e}",
                metadata={
                    "command": command,
                    "cwd": str(working_directory)
                    if working_directory
                    else None,
                    "timeout": timeout,
                    "exit_code": None,
                    "duration": duration,
                    "executed": False,
                    "confirmed": True,
                },
            )

    def __repr__(self) -> str:
        return "<Tool name='Shell'>"

