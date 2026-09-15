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
    DEFAULT_TIMEOUT = 120
    BACKGROUND_START_CHECK_SECONDS = 0.15

    description = (
        "Execute shell commands. Use background=true for long-running "
        "processes such as web servers, development servers, watchers, "
        "or commands that must remain running while the agent continues. "
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
                    "Maximum execution time in seconds for synchronous commands. "
                    "If omitted, uses 120 seconds."
                ),
                "default": DEFAULT_TIMEOUT,
            },
            "background": {
                "type": "boolean",
                "description": (
                    "Start the command without waiting for it to finish. "
                    "Set to true for long-running servers, watchers, or other "
                    "processes that must stay alive while the agent continues. "
                    "Returns the PID immediately."
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
    def _bounded_output(cls, value: str) -> tuple[str, bool]:
        value = str(value or "").strip()

        if len(value) <= cls.MAX_OUTPUT_CHARS:
            return value, False

        head = int(cls.MAX_OUTPUT_CHARS * 0.60)
        tail = cls.MAX_OUTPUT_CHARS - head

        return (
            value[:head].rstrip()
            + "\n\n... OUTPUT TRUNCATED ...\n\n"
            + value[-tail:].lstrip(),
            True,
        )

    @staticmethod
    def _process_group_kwargs() -> dict:
        """Create platform-specific isolation for background processes."""
        if os.name == "nt":
            return {
                "creationflags": subprocess.CREATE_NEW_PROCESS_GROUP,
            }

        return {
            "start_new_session": True,
        }

    @staticmethod
    def _terminate_process_group(process: subprocess.Popen) -> None:
        """Best-effort termination of a process and its children."""
        try:
            if process.poll() is not None:
                return

            if os.name == "nt":
                process.send_signal(signal.CTRL_BREAK_EVENT)
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    process.kill()
            else:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait(timeout=2)
        except (ProcessLookupError, PermissionError, OSError):
            try:
                process.kill()
            except (ProcessLookupError, PermissionError, OSError):
                pass

    def _run_background(
        self,
        command: str,
        working_directory: Optional[Path],
        confirm: str,
    ) -> ToolResult:
        log_path = (
            working_directory if working_directory else Path.cwd()
        ) / ".evana_shell_background.log"

        start_time = time.perf_counter()

        try:
            log_file = open(
                log_path,
                "w",
                encoding="utf-8",
                errors="replace",
            )

            process = subprocess.Popen(
                command,
                shell=True,
                cwd=(str(working_directory) if working_directory else None),
                stdin=subprocess.DEVNULL,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                text=True,
                **self._process_group_kwargs(),
            )

            # Keep the file descriptor owned by the child process' output
            # redirection. The parent no longer needs its Python handle.
            log_file.close()

            # Give commands a short window to fail immediately. This catches
            # cases such as "Address already in use" instead of falsely
            # reporting a dead server as successfully started.
            time.sleep(self.BACKGROUND_START_CHECK_SECONDS)
            return_code = process.poll()

            if return_code is not None:
                try:
                    output = log_path.read_text(
                        encoding="utf-8",
                        errors="replace",
                    )
                except OSError:
                    output = ""

                bounded_output, truncated = self._bounded_output(output)
                content = (
                    "Background process exited immediately.\n"
                    f"PID: {process.pid}\n"
                    f"Exit code: {return_code}\n"
                    f"Log file: {log_path}"
                )

                if bounded_output:
                    content += f"\n\nOUTPUT:\n{bounded_output}"

                return ToolResult(
                    success=False,
                    content=content,
                    metadata={
                        "command": command,
                        "cwd": str(working_directory) if working_directory else None,
                        "background": True,
                        "pid": process.pid,
                        "process_group": process.pid if os.name != "nt" else None,
                        "exit_code": return_code,
                        "log_file": str(log_path),
                        "output": output,
                        "output_truncated": truncated,
                        "duration": time.perf_counter() - start_time,
                        "executed": True,
                        "confirmed": True,
                    },
                )

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
                    "cwd": str(working_directory) if working_directory else None,
                    "background": True,
                    "pid": process.pid,
                    "process_group": process.pid if os.name != "nt" else None,
                    "log_file": str(log_path),
                    "duration": time.perf_counter() - start_time,
                    "executed": True,
                    "confirmed": True,
                },
            )

        except (OSError, PermissionError) as e:
            return ToolResult(
                success=False,
                content=f"Background shell execution failed: {e}",
                metadata={
                    "command": command,
                    "cwd": str(working_directory) if working_directory else None,
                    "background": True,
                    "duration": time.perf_counter() - start_time,
                    "executed": False,
                    "confirmed": confirm == "Y",
                },
            )

    def execute(
        self,
        command: str,
        cwd: Optional[str] = None,
        timeout: int = DEFAULT_TIMEOUT,
        background: bool = False,
        confirm: str = "Y",
    ) -> ToolResult:
        blocked_patterns = [
            r"rm\s+-rf\s+/",
            r":\(\)\{.*\};:",
            r"mkfs\.",
            r"dd\s+if=.*of=/dev/",
        ]

        for pattern in blocked_patterns:
            if re.search(pattern, command or ""):
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
                content="Command execution cancelled. Confirmation Y is required.",
                metadata={
                    "command": command,
                    "executed": False,
                    "confirmed": False,
                },
            )

        if timeout is None:
            timeout = self.DEFAULT_TIMEOUT

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

        if background:
            return self._run_background(
                command=command,
                working_directory=working_directory,
                confirm=confirm,
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
                success=process.returncode == 0,
                content="\n\n".join(output_parts),
                metadata={
                    "command": command,
                    "cwd": str(working_directory) if working_directory else None,
                    "timeout": timeout,
                    "background": False,
                    "exit_code": process.returncode,
                    "stdout": stdout,
                    "stderr": stderr,
                    "stdout_truncated": stdout_truncated,
                    "stderr_truncated": stderr_truncated,
                    "output_limit_chars": self.MAX_OUTPUT_CHARS,
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
                stdout = stdout.decode("utf-8", errors="replace")
            if isinstance(stderr, bytes):
                stderr = stderr.decode("utf-8", errors="replace")

            bounded_stdout, stdout_truncated = self._bounded_output(stdout)
            bounded_stderr, stderr_truncated = self._bounded_output(stderr)

            output = f"Command timed out after {timeout} seconds."
            if bounded_stdout:
                output += f"\n\nSTDOUT:\n{bounded_stdout}"
            if bounded_stderr:
                output += f"\n\nSTDERR:\n{bounded_stderr}"

            return ToolResult(
                success=False,
                content=output,
                metadata={
                    "command": command,
                    "cwd": str(working_directory) if working_directory else None,
                    "timeout": timeout,
                    "background": False,
                    "exit_code": None,
                    "stdout": stdout,
                    "stderr": stderr,
                    "stdout_truncated": stdout_truncated,
                    "stderr_truncated": stderr_truncated,
                    "output_limit_chars": self.MAX_OUTPUT_CHARS,
                    "duration": duration,
                    "executed": True,
                    "confirmed": True,
                    "timed_out": True,
                },
            )

        except FileNotFoundError as e:
            return ToolResult(
                success=False,
                content=f"Command execution failed: {e}",
                metadata={
                    "command": command,
                    "cwd": str(working_directory) if working_directory else None,
                    "timeout": timeout,
                    "background": False,
                    "exit_code": None,
                    "duration": time.perf_counter() - start_time,
                    "executed": False,
                    "confirmed": True,
                },
            )

        except PermissionError:
            return ToolResult(
                success=False,
                content="Permission denied while executing command.",
                metadata={
                    "command": command,
                    "cwd": str(working_directory) if working_directory else None,
                    "timeout": timeout,
                    "background": False,
                    "exit_code": None,
                    "duration": time.perf_counter() - start_time,
                    "executed": False,
                    "confirmed": True,
                },
            )

        except Exception as e:
            return ToolResult(
                success=False,
                content=f"Shell execution error: {e}",
                metadata={
                    "command": command,
                    "cwd": str(working_directory) if working_directory else None,
                    "timeout": timeout,
                    "background": False,
                    "exit_code": None,
                    "duration": time.perf_counter() - start_time,
                    "executed": False,
                    "confirmed": True,
                },
            )

    def __repr__(self) -> str:
        return "<Tool name='Shell'>"
