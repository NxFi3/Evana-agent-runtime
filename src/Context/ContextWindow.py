class ContextWindow:
    def __init__(self):
        self.system = "" # system Instruction
        self.task = "" # developer instructions
        self.trajectory = "" # current trajectory of the agent previous steps tools results agent responses..
        self.plans = "" # plan instructions
        self.user = "" # user input

    def set_system(self, content: str):
        self.system = content

    def set_task(self, content: str):
        self.task = content
    def set_trajectory(self, content: str):
        self.trajectory = content

    def set_plans(self, content: str):
        self.plans = content

    def set_user(self, content: str):
        self.user = content

    def prompt(self) -> str:
     return f"""
## System
{self.system}

## Developer Instructions
{self.task}

## Plan
{self.plans}

## Trajectory
{self.trajectory}

## User Input
{self.user}
""".strip()