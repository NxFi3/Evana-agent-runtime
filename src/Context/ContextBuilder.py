from typing import List
from src.Context.ContextWindow import ContextWindow, Message
from src.Utils.logger import get_logger
from src.Memory.MemoryEvent import MemoryEvent

logger = get_logger('[CONTEXTBUILDER]')


class ContextBuilder:
    def __init__(self, context_window: ContextWindow):
        self.context_window = context_window
        self.DeveloperInstructions_path = 'agentInstructions/DeveloperInstructions.md'
        self.Systemnstructions_path = 'agentInstructions/SystemInstructions.md'

    def _load_developer_instructions(self) -> str:
        try:
            with open(self.DeveloperInstructions_path, 'r') as file:
                return file.read()
        except FileNotFoundError:
            logger.warning(f"Developer instructions file not found at {self.DeveloperInstructions_path}.")
            return ""
        except Exception as e:
            logger.error(f"Error loading developer instructions: {e}")
            return ""

    def _load_tool_instructions(self) -> str:
        try:
            with open(self.Systemnstructions_path, 'r') as file:
                return file.read()
        except FileNotFoundError:
            logger.warning(f"Tool instructions file not found at {self.Systemnstructions_path}.")
            return ""
        except Exception as e:
            logger.error(f"Error loading tool instructions: {e}")
            return ""

    def _event_to_message(self, event: MemoryEvent) -> Message:
        event_type = event.event_type.lower()
        if event_type == 'user_input':
            return {"role": "user", "content": event.content}
        if event_type == 'agent_action':
            return {"role": "assistant", "content": event.content}
        if event_type == 'tool_result':
            message: Message = {"role": "tool", "content": event.content,'metadata':event.metadata}
            tool_name = event.metadata.get("tool_name")
            if tool_name:
                message["name"] = tool_name
            return message
        if event_type == 'tool_call':
            tool_name = event.metadata.get("tool_name")
            arguments = event.metadata.get("arguments")
            if tool_name:
                return {
                    "role": "assistant",
                    "content": event.content,
                    "tool_calls": [{
                        "id": str(event.metadata.get("tool_call_id", event.id)),
                        "type": "function",
                        "function": {
                            "name": tool_name,
                            "arguments": arguments if arguments is not None else {},
                        },
                    }],
                }
            return {"role": "assistant", "content": event.content}
        return {
            "role": "assistant",
            "content": f"Step {event.step}: {event.event_type} {event.content}".strip(),
        }

    def build_context(self, User_input: str = '', STM_Result: List[MemoryEvent] = None):
        events = STM_Result or []
        trajectory = [self._event_to_message(event) for event in events]
        self.context_window.set_trajectory(trajectory)
        self.context_window.set_user(User_input)
        self.context_window.set_system(self._load_tool_instructions())
        self.context_window.set_task(self._load_developer_instructions())
        return self.context_window.prompt()
