from datetime import datetime, timezone

from src.Context.ContextWindow import ContextWindow
from src.Context.ContextBuilder import ContextBuilder
from src.Context.ContextManager import ContextManager
from src.Context.TokenBudget import TokenBudget
from src.Memory.MemoryEvent import MemoryEvent


class FakeLLMProvider:

    class FakeModel:
        options = {"num_ctx": 131072}

        def get_model_context_length(self):
            return 131072

    def __init__(self):
        self.model = self.FakeModel()


class FakeCompactor:

    def compact(self, context, max_length):
        return context


def create_events():

    event_types = [
        "user_input",
        "agent_action",
        "tool_call",
        "tool_result",
        "agent_response",
        "memory",
        "observation",
        "decision",
    ]

    events = []

    for step in range(1, 101):

        event_type = event_types[(step - 1) % len(event_types)]

        events.append(
            MemoryEvent(
                id=step,
                event_type=event_type,
                content=(
                    f"EVENT_CONTENT "
                    f"step={step} "
                    f"type={event_type} "
                    f"UNIQUE_MARKER_{step}"
                ),
                source="test",
                step=step,
                timestamp=datetime.now(timezone.utc),
                metadata={
                    "test": True,
                    "step": step,
                    "event_type": event_type,
                },
            )
        )

    return events


def main():

    print("=" * 100)
    print("EVANA CONTEXT EVENT TYPE TEST")
    print("=" * 100)

    context_window = ContextWindow()
    context_builder = ContextBuilder(context_window)

    llm_provider = FakeLLMProvider()

    token_budget = TokenBudget(
        {
            "token_budget": 131072,
            "safe_margin": 1000,
        },
        llm_provider,
    )

    compactor = FakeCompactor()

    context_manager = ContextManager(
        context_builder,
        compactor,
        token_budget,
    )

    events = create_events()

    print(f"\nCreated events: {len(events)}")

    prompt = context_manager.build_agent_context(
        PreviousResponse={
            "prompt_eval_count": 0,
            "eval_count": 0,
        },
        User_input="CURRENT USER INPUT",
        STM_Result=events,
    )

    print("\n")
    print("=" * 100)
    print("RAW CONTEXT")
    print("=" * 100)

    print(prompt)

    print("\n")
    print("=" * 100)
    print("VALIDATION")
    print("=" * 100)

    # ---------------------------------------------------------
    # Check every step
    # ---------------------------------------------------------

    missing_steps = []
    duplicate_steps = []

    for step in range(1, 101):

        marker = f"UNIQUE_MARKER_{step}"
        count = prompt.count(marker)

        if count == 0:
            missing_steps.append(step)

        elif count > 1:
            duplicate_steps.append((step, count))

    print(f"Missing steps:   {missing_steps}")
    print(f"Duplicate steps: {duplicate_steps}")

    # ---------------------------------------------------------
    # Check user_input events
    # ---------------------------------------------------------

    user_input_steps = [
        event.step
        for event in events
        if event.event_type.lower() == "user_input"
    ]

    print(f"User input event steps: {user_input_steps}")

    # ---------------------------------------------------------
    # Final checks
    # ---------------------------------------------------------

    if missing_steps:
        print("\n❌ FAIL: Some events disappeared from context.")

    elif duplicate_steps:
        print("\n❌ FAIL: Some events were duplicated.")

    else:
        print("\n✅ PASS: All 100 events exist exactly once.")

    print("\n")
    print("=" * 100)
    print("END TEST")
    print("=" * 100)


if __name__ == "__main__":
    main()