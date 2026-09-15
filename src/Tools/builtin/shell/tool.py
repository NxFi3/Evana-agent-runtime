import os
import re
import signal
import subprocess
import time
from pathlib import Path
from typing import Optional

from src.Tools.Tool import Tool
from src.Tools.ToolResult import ToolResult


class Shell(Tool):

    name = "Shell"

    MAX_OUTPUT_CHARS = 2400

    description = (
        "Execute shell commands. Use background=true for long-running "
        "processes such as web servers, development servers, watchers, "
        "or any command that must remain running while the agent continues. "
        "Background execution returns immediately with the process PID. "
        "Use background=false for commands that should finish before continuing."
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
                    "Maximum execution time in seconds for synchronous "
                    "commands. If omitted, uses 120 seconds."
                ),
                "default": 120,
            },
            "background": {
                "type": "boolean",
                "description": (
                    "Start the command without waiting for it to finish. "
                    "Set to true for long-running servers or processes. "
                    "Set to false for normal commands."
                ),
                "default": False,
            },
            "confirm": {
                "type": "string",
                "enum": ["Y", "N"],
                "description": (
                    "Set to Y to execute the command. " "Set to N to cancel execution."
                ),
                "default": "Y",
            },
        },
        "required": ["command"],
    }

    @classmethod
    def _bounded_output(
        cls,
        value: str,
    ) -> tuple[str, bool]:

        value = str(value or "").strip()

        if len(value) <= cls.MAX_OUTPUT_CHARS:
            return value, False

        head = int(cls.MAX_OUTPUT_CHARS * 0.60)

        tail = cls.MAX_OUTPUT_CHARS - head

        return (
            value[:head].rstrip()
            + "\n\n"
            + "... OUTPUT TRUNCATED ...\n\n"
            + value[-tail:].lstrip(),
            True,
        )

    @staticmethod
    def _resolve_working_directory(
        cwd: Optional[str],
    ) -> Optional[Path]:

        if not cwd:
            return None

        working_directory = Path(cwd)

        if not working_directory.exists():
            raise FileNotFoundError(f"Working directory not found: {cwd}")

        if not working_directory.is_dir():
            raise NotADirectoryError(f"Working directory is not a directory: {cwd}")

        return working_directory

    @staticmethod
    def _background_log_path(
        working_directory: Optional[Path],
    ) -> Path:

        if working_directory:
            return working_directory / ".evana_shell_background.log"

        return Path(".evana_shell_background.log")

    def _execute_background(
        self,
        command: str,
        working_directory: Optional[Path],
        timeout: int,
    ) -> ToolResult:

        log_path = self._background_log_path(working_directory)

        try:
            log_file = open(
                log_path,
                "a",
                encoding="utf-8",
                buffering=1,
            )

            start_time = time.perf_counter()

            try:
                process = subprocess.Popen(
                    command,
                    shell=True,
                    cwd=(str(working_directory) if working_directory else None),
                    stdin=subprocess.DEVNULL,
                    stdout=log_file,
                    stderr=subprocess.STDOUT,
                    text=True,
                    start_new_session=True,
                )

            except Exception:
                log_file.close()
                raise

            log_file.write(
                "\n"
                + "=" * 72
                + "\n"
                + f"Command: {command}\n"
                + f"PID: {process.pid}\n"
                + f"Started: {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
                + "=" * 72
                + "\n"
            )

            log_file.close()

            duration = time.perf_counter() - start_time

            return ToolResult(
                success=True,
                content=(
                    "Background process started successfully.\n"
                    f"PID: {process.pid}\n"
                    f"Command: {command}\n"
                    f"Log file: {log_path}"
                ),
                metadata={
                    "command": command,
                    "cwd": (str(working_directory) if working_directory else None),
                    "timeout": timeout,
                    "pid": process.pid,
                    "background": True,
                    "log_file": str(log_path),
                    "started": True,
                    "duration": duration,
                    "executed": True,
                    "confirmed": True,
                },
            )

        except Exception as e:
            return ToolResult(
                success=False,
                content=("Failed to start background process: " f"{e}"),
                metadata={
                    "command": command,
                    "cwd": (str(working_directory) if working_directory else None),
                    "timeout": timeout,
                    "background": True,
                    "started": False,
                    "executed": False,
                    "confirmed": True,
                },
            )

    def execute(
        self,
        command: str,
        cwd: Optional[str] = None,
        timeout: int = 120,
        background: bool = False,
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
                command or "",
            ):
                return ToolResult(
                    success=False,
                    content="Command blocked for safety.",
                )

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
                content=("Command execution cancelled. " "Confirmation Y is required."),
                metadata={
                    "command": command,
                    "executed": False,
                    "confirmed": False,
                },
            )

        if timeout is None:
            timeout = 120

        if (
            not isinstance(
                timeout,
                int,
            )
            or timeout <= 0
        ):
            return ToolResult(
                success=False,
                content="Timeout must be a positive integer.",
            )

        try:
            working_directory = self._resolve_working_directory(cwd)

        except FileNotFoundError as e:
            return ToolResult(
                success=False,
                content=str(e),
            )

        except NotADirectoryError as e:
            return ToolResult(
                success=False,
                content=str(e),
            )

        if background:
            return self._execute_background(
                command=command,
                working_directory=working_directory,
                timeout=timeout,
            )

        start_time = time.perf_counter()

        try:
            process = subprocess.run(
                command,
                shell=True,
                cwd=(str(working_directory) if working_directory else None),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
            )

            duration = time.perf_counter() - start_time

            stdout = process.stdout or ""
            stderr = process.stderr or ""

            bounded_stdout, stdout_truncated = self._bounded_output(stdout)

            bounded_stderr, stderr_truncated = self._bounded_output(stderr)

            success = process.returncode == 0

            output_parts = []

            if bounded_stdout:
                output_parts.append(f"STDOUT:\n{bounded_stdout}")

            if bounded_stderr:
                output_parts.append(f"STDERR:\n{bounded_stderr}")

            if not output_parts:
                output_parts.append("Command completed with no output.")

            output_parts.append(f"Exit code: {process.returncode}")

            if stdout_truncated or stderr_truncated:
                output_parts.append("Output truncated for agent context.")

            return ToolResult(
                success=success,
                content="\n\n".join(output_parts),
                metadata={
                    "command": command,
                    "cwd": (str(working_directory) if working_directory else None),
                    "timeout": timeout,
                    "background": False,
                    "exit_code": process.returncode,
                    "stdout": stdout,
                    "stderr": stderr,
                    "stdout_truncated": stdout_truncated,
                    "stderr_truncated": stderr_truncated,
                    "output_limit_chars": (self.MAX_OUTPUT_CHARS),
                    "duration": duration,
                    "executed": True,
                    "confirmed": True,
                },
            )

        except subprocess.TimeoutExpired as e:

            duration = time.perf_counter() - start_time

            stdout = e.stdout or ""
            stderr = e.stderr or ""

            if isinstance(
                stdout,
                bytes,
            ):
                stdout = stdout.decode(
                    "utf-8",
                    errors="replace",
                )

            if isinstance(
                stderr,
                bytes,
            ):
                stderr = stderr.decode(
                    "utf-8",
                    errors="replace",
                )

            bounded_stdout, stdout_truncated = self._bounded_output(stdout)

            bounded_stderr, stderr_truncated = self._bounded_output(stderr)

            output = f"Command timed out after " f"{timeout} seconds."

            if bounded_stdout:
                output += f"\n\nSTDOUT:\n" f"{bounded_stdout}"

            if bounded_stderr:
                output += f"\n\nSTDERR:\n" f"{bounded_stderr}"

            return ToolResult(
                success=False,
                content=output,
                metadata={
                    "command": command,
                    "cwd": (str(working_directory) if working_directory else None),
                    "timeout": timeout,
                    "background": False,
                    "exit_code": None,
                    "stdout": stdout,
                    "stderr": stderr,
                    "stdout_truncated": stdout_truncated,
                    "stderr_truncated": stderr_truncated,
                    "output_limit_chars": (self.MAX_OUTPUT_CHARS),
                    "duration": duration,
                    "executed": True,
                    "confirmed": True,
                    "timed_out": True,
                },
            )

        except FileNotFoundError as e:

            duration = time.perf_counter() - start_time

            return ToolResult(
                success=False,
                content=(f"Command execution failed: {e}"),
                metadata={
                    "command": command,
                    "cwd": (str(working_directory) if working_directory else None),
                    "timeout": timeout,
                    "background": False,
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
                content=("Permission denied while " "executing command."),
                metadata={
                    "command": command,
                    "cwd": (str(working_directory) if working_directory else None),
                    "timeout": timeout,
                    "background": False,
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
                content=(f"Shell execution error: {e}"),
                metadata={
                    "command": command,
                    "cwd": (str(working_directory) if working_directory else None),
                    "timeout": timeout,
                    "background": False,
                    "exit_code": None,
                    "duration": duration,
                    "executed": False,
                    "confirmed": True,
                },
            )

    def __repr__(self) -> str:
        return "<Tool name='Shell'>"
