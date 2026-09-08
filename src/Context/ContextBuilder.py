#src/Context/ContextBuilder.py

from typing import List
from src.Context.ContextWindow import ContextWindow 
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
    def build_context(self,User_input:str='',STM_Result:List[MemoryEvent]=[]):
        Trajectory = "\n".join([f"Step {event.step}: {event.event_type} {event.content}" for event in STM_Result])
        user_inputs = f"{User_input}"
        
        self.context_window.set_trajectory(Trajectory)
        self.context_window.set_user(user_inputs)
        self.context_window.set_system(self._load_tool_instructions())
        self.context_window.set_task(self._load_developer_instructions())
        return self.context_window.prompt()



