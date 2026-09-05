#src/Context/ContextManager.py

from src.Utils.logger import get_logger
from src.Context.ContextBuilder import ContextBuilder
from src.Context.Compactor import Compactor

logger = get_logger('[CONTEXTMANAGER]')

class ContextManager:
    def __init__(self, context_builder: ContextBuilder, compactor: Compactor):
        self.context_builder = context_builder
        self.compactor = compactor

    def check_context_length(self, max_length: int) -> None:
        if len(self.context_builder.context_window.trajectory) > max_length:
            logger.warning("Context length exceeds max length. Compacting context.")
            self.context_builder.context_window.trajectory = self.compactor.compact(
                self.context_builder.context_window.trajectory,
                max_length
            )

        if len(self.context_builder.context_window.user) > max_length:
            logger.warning("User input length exceeds max length. Compacting user input.")
            self.context_builder.context_window.user = self.compactor.compact(
                self.context_builder.context_window.user,
                max_length
            )

    def Build_Agent_context(
        self,
        User_input: str = '',
        STM_Result: list = [],
        max_length: int = 24000
    ) -> str:
        self.context_builder.build_context(User_input, STM_Result)
        self.check_context_length(max_length)
        return self.context_builder.context_window.prompt()