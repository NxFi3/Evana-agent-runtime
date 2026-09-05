# src/Context/ContextManager.py

from src.Utils.logger import get_logger
from src.Context.ContextBuilder import ContextBuilder
from src.Context.Compactor import Compactor

logger = get_logger('[CONTEXTMANAGER]')


class ContextManager:
    def __init__(self, context_builder: ContextBuilder, compactor: Compactor):
        self.context_builder = context_builder
        self.compactor = compactor
        self.compacted_trajectory = None
        self.compacted_until_step = 0

    def check_context_length(self, max_length: int) -> bool:
        compacted = False

        if len(self.context_builder.context_window.trajectory) > max_length:
            logger.warning(
                "Context length exceeds max length. Compacting context."
            )

            self.context_builder.context_window.trajectory = (
                self.compactor.compact(
                    self.context_builder.context_window.trajectory,
                    max_length
                )
            )

            compacted = True

        if len(self.context_builder.context_window.user) > max_length:
            logger.warning(
                "User input length exceeds max length. Compacting user input."
            )

            self.context_builder.context_window.user = (
                self.compactor.compact(
                    self.context_builder.context_window.user,
                    max_length
                )
            )

        return compacted

    def Build_Agent_context(
        self,
        User_input: str = '',
        STM_Result: list = [],
        max_length: int = 24000
    ) -> str:

        if not STM_Result:
            self.context_builder.build_context(
                User_input,
                []
            )

            self.check_context_length(max_length)

            return self.context_builder.context_window.prompt()

        current_step = STM_Result[-1].step

        if self.compacted_trajectory is None:
            previous_events = STM_Result[:-1]

            self.context_builder.build_context(
                User_input,
                previous_events
            )

            trajectory = self.context_builder.context_window.trajectory

        else:
            new_events = [
                event
                for event in STM_Result
                if event.step > self.compacted_until_step
            ]

            trajectory = self.compacted_trajectory

            if new_events:
                trajectory += "\n" + "\n".join(
                    f"Step {event.step}: {event.content}"
                    for event in new_events
                    if event.event_type.lower() != 'user_input'
                )

            self.context_builder.build_context(
                User_input,
                []
            )

        self.context_builder.context_window.trajectory = trajectory

        was_compacted = self.check_context_length(max_length)

        if was_compacted:
            self.compacted_trajectory = (
                self.context_builder.context_window.trajectory
            )
            self.compacted_until_step = current_step

        return self.context_builder.context_window.prompt()