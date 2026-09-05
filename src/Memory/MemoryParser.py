#src/Memory/MemoryParser.py

import json


class MemoryParser:

    VALID_DECISION = "CREATE"

    def parse(self, response: str) -> list:
        if not isinstance(response, str):
            raise TypeError("LLM response must be a string.")

        response = response.strip()

        if not response:
            raise ValueError("LLM response is empty.")

        try:
            data = json.loads(response)
        except json.JSONDecodeError as e:
            raise ValueError(
                f"Invalid JSON returned by LLM: {e}"
            ) from e

        if not isinstance(data, list):
            raise ValueError("Memory output must be a JSON list.")

        results = []

        for index, item in enumerate(data):
            if not isinstance(item, dict):
                raise ValueError(
                    f"Memory item at index {index} must be an object."
                )

            results.append(self._validate_item(item, index))

        return results

    def _validate_item(self, item: dict, index: int) -> dict:
        required_fields = {
            "decision",
            "content",
            "event_id"
        }

        if set(item.keys()) != required_fields:
            raise ValueError(
                f"Invalid fields at index {index}. "
                f"Expected exactly: {required_fields}"
            )

        if item["decision"] != self.VALID_DECISION:
            raise ValueError(
                f"Invalid decision at index {index}: "
                f"{item['decision']}"
            )

        content = item["content"]

        if not isinstance(content, str):
            raise ValueError(
                f"'content' at index {index} must be a string."
            )

        content = content.strip()

        if not content:
            raise ValueError(
                f"'content' at index {index} cannot be empty."
            )

        event_id = item["event_id"]

        if isinstance(event_id, bool) or not isinstance(event_id, int):
            raise ValueError(
                f"'event_id' at index {index} must be an integer."
            )

        return {
            "decision": self.VALID_DECISION,
            "content": content,
            "event_id": event_id
        }