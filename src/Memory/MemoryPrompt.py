#src/Memory/MemoryPrompt.py

def build_decision_prompt(context: str) -> str:
    return f"""
You are the memory consolidation component of an AI agent.

Your task is to identify information from the provided events that is worth storing as long-term memory.

Only create a memory when the information is:
- useful for future interactions
- stable or likely to remain relevant
- specific enough to be represented as a memory
- not merely a temporary conversational detail

Do not create memories for:
- greetings or casual conversation
- temporary states
- requests that do not contain reusable information
- tool execution details unless they contain useful persistent information
- information that is already sufficiently represented by the related memory

For every piece of information that should be stored, return one object.

Output ONLY valid JSON.
The output must be a JSON list.

Each object must contain exactly these fields:
- "decision": must always be "CREATE"
- "content": a concise, self-contained memory statement
- "event_id": the ID of the source event

If no information should be stored, return an empty list.

Example:

[
  {{
    "decision": "CREATE",
    "content": "The user is building an AI agent runtime called Evana.",
    "event_id": 42
  }}
]

Input events:

{context}
"""