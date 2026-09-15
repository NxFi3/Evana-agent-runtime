from typing import List, Optional

from src.Context.ContextWindow import ContextWindow, Message
from src.Utils.logger import get_logger
from src.Memory.MemoryEvent import MemoryEvent
from src.Agent.AgentState import AgentState

logger = get_logger("[CONTEXTBUILDER]")


class ContextBuilder:

    def __init__(
        self,
        context_window: ContextWindow,
    ):
        self.context_window = context_window

        self.DeveloperInstructions_path = "agentInstructions/DeveloperInstructions.md"

        self.SystemInstructions_path = "agentInstructions/SystemInstructions.md"

    def _load_developer_instructions(self) -> str:

        try:

            with open(
                self.DeveloperInstructions_path,
                "r",
                encoding="utf-8",
            ) as file:

                return file.read()

        except FileNotFoundError:

            logger.warning(
                "Developer instructions file not found at "
                f"{self.DeveloperInstructions_path}."
            )

            return ""

        except Exception as e:

            logger.error(f"Error loading developer instructions: {e}")

            return ""

    def _load_system_instructions(self) -> str:

        try:

            with open(
                self.SystemInstructions_path,
                "r",
                encoding="utf-8",
            ) as file:

                return file.read()

        except FileNotFoundError:

            logger.warning(
                "System instructions file not found at "
                f"{self.SystemInstructions_path}."
            )

            return ""

        except Exception as e:

            logger.error(f"Error loading system instructions: {e}")

            return ""

    def _event_to_message(
        self,
        event: MemoryEvent,
    ) -> Message:

        event_type = str(event.event_type).lower()

        if event_type == "agent_action":

            return {
                "role": "assistant",
                "content": event.content,
            }

        if event_type == "tool_call":

            metadata = event.metadata if event.metadata else {}

            tool_call = metadata.get("tool_call")

            if isinstance(
                tool_call,
                dict,
            ) and tool_call.get("function"):

                return {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [tool_call],
                }

            # A tool call without structured data is not
            # useful as a synthetic assistant message.
            return {
                "role": "assistant",
                "content": event.content or "",
            }

        if event_type == "tool_result":

            return {
                "role": "tool",
                "content": event.content or "",
            }

        return {
            "role": "assistant",
            "content": (
                f"Step {event.step}: " f"{event.event_type} " f"{event.content}"
            ).strip(),
        }

    def set_workspace(
        self,
        root: str,
        state: str = "",
    ):

        self.context_window.set_workspace(
            root,
            state,
        )

    def _build_agent_state(
        self,
        agent_state: AgentState,
    ) -> str:

        return "\n".join(
            [
                "Current agent state:",
                f"Phase: " f"{agent_state.phase or 'unknown'}",
                f"Iteration: " f"{agent_state.iteration}",
                ("Completion: " f"{'true' if agent_state.completion else 'false'}"),
            ]
        )

    def build_context(
        self,
        user_input: str = "",
        stm_result: Optional[List[Message]] = None,
        agent_state: Optional[AgentState] = None,
        compacted_history: Optional[List[Message]] = None,
    ):

        recent_history = stm_result or []

        compacted_history = compacted_history or []

        self.context_window.set_system(self._load_system_instructions())

        self.context_window.set_skills(self._load_developer_instructions())

        self.context_window.set_user(user_input)

        if agent_state:

            self.context_window.set_agent_state(self._build_agent_state(agent_state))

            self.context_window.set_workspace(agent_state.workspace_root)

            self.context_window.set_workspace_files([])

        else:

            self.context_window.set_agent_state("")

            self.context_window.set_workspace("")

            self.context_window.set_workspace_files([])

        self.context_window.set_task("")

        self.context_window.set_last_action("")

        self.context_window.set_last_observation("")

        self.context_window.set_compacted_history(compacted_history)

        self.context_window.set_history(recent_history)

        return self.context_window.prompt()
