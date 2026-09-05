class ContextWindow:
    def __init__(self):
        self.system = "" # system Instruction
        self.task = "" # developer instructions
        self.trajectory = "" # current trajectory of the agent previous steps tools results agent responses..
        self.tools = "" # tool use instructions  
        self.user = "" # user input

    def set_system(self, content: str):
        self.system = content

    def set_task(self, content: str):
        self.task = content
    def set_trajectory(self, content: str):
        self.trajectory = content

    def set_tools(self, content: str):
        self.tools = content

    def set_user(self, content: str):
        self.user = content

    def prompt(self) -> str:
        return f"""
## System
{self.system}

## Available Tools
{self.tools}

## Developer Instructions
{self.task}

## User Input
{self.user}

## Trajectory
{self.trajectory}

## Next Steps
""".strip()