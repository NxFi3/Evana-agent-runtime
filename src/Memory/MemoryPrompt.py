#src/Memory/MemoryPrompt.py

def build_decision_prompt(context: str) -> str:
    return f"""
You are the memory consolidation component of an AI agent.

Your task is to identify information from the provided events that is worth storing as long-term memory.

Create a memory only when the information is:
- useful for future interactions
- stable or likely to remain relevant
- specific and self-contained
- explicitly supported by the provided events

Do not create memories for:
- greetings or casual conversation
- temporary states
- one-time requests without reusable information
- tool execution details unless they contain persistent information
- information already sufficiently represented by a related memory
- guesses, assumptions, or information not explicitly supported by the events

Do not invent or infer facts that are not present in the input.

For every piece of information that should be stored, return one object.

Output ONLY valid JSON.
Do not use markdown or code fences.
The output must be a JSON list.

Each object must contain exactly these fields:
- "decision": must always be "CREATE"
- "content": a concise, self-contained memory statement

If no information should be stored, return an empty list.

Example:

[
  {{
    "decision": "CREATE",
    "content": "The user is building an AI agent runtime called Evana."
  }}
]

Input events:

{context}
"""