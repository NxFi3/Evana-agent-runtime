import json
from typing import Any

from src.Utils.logger import get_logger


class ToolDispatcher:
    """
    Parse and validate model-generated tool calls before execution.

    The dispatcher is intentionally conservative:
    - it never guesses missing required arguments;
    - it never silently changes argument values;
    - malformed calls are returned as structured validation failures.
    """

    def __init__(self):
        self.logger = get_logger("[DISPATCHER]")

    def _extract_tool_call(
        self,
        tool_call: Any,
    ) -> tuple[str, Any, str | None, str]:
        """
        Return:
            name,
            arguments,
            call_id,
            call_type
        """

        if hasattr(tool_call, "function"):
            function = tool_call.function

            name = getattr(function, "name", None)
            arguments = getattr(function, "arguments", {})
            call_id = getattr(tool_call, "id", None)
            call_type = getattr(tool_call, "type", "function")

            return (
                str(name).strip() if name is not None else "",
                arguments,
                call_id,
                str(call_type or "function"),
            )

        if isinstance(tool_call, dict):
            function = tool_call.get("function", {})

            if not isinstance(function, dict):
                return (
                    "",
                    {},
                    tool_call.get("id"),
                    tool_call.get(
                        "type",
                        "function",
                    ),
                )

            name = function.get("name")
            arguments = function.get("arguments", {})
            call_id = tool_call.get("id")
            call_type = tool_call.get("type", "function")

            return (
                str(name).strip() if name is not None else "",
                arguments,
                call_id,
                str(call_type or "function"),
            )

        raise TypeError("Invalid tool call format.")

    def _parse_arguments(
        self,
        arguments: Any,
    ) -> dict:
        if arguments is None:
            return {}

        if isinstance(arguments, dict):
            return dict(arguments)

        if isinstance(arguments, str):
            text = arguments.strip()

            if not text:
                return {}

            try:
                parsed = json.loads(text)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid tool arguments JSON: {exc}") from exc

            if not isinstance(parsed, dict):
                raise TypeError("Tool arguments JSON must decode to an object.")

            return parsed

        raise TypeError("Tool arguments must be an object or JSON object string.")

    def _matches_type(
        self,
        value: Any,
        expected_type: str,
    ) -> bool:
        """
        Minimal JSON-schema-compatible type validation.

        Supported:
            string
            integer
            number
            boolean
            object
            array
            null
        """

        if expected_type == "string":
            return isinstance(value, str)

        if expected_type == "integer":
            return isinstance(value, int) and not isinstance(value, bool)

        if expected_type == "number":
            return isinstance(value, (int, float)) and not isinstance(value, bool)

        if expected_type == "boolean":
            return isinstance(value, bool)

        if expected_type == "object":
            return isinstance(value, dict)

        if expected_type == "array":
            return isinstance(value, list)

        if expected_type == "null":
            return value is None

        # Unknown schema types should not make otherwise valid tools fail.
        return True

    def validate(
        self,
        arguments: dict,
        parameters: dict | None,
    ) -> tuple[bool, str]:
        """
        Validate tool arguments against a tool definition.

        This intentionally validates only the common JSON-schema fields
        used by the builtin tools.
        """

        parameters = parameters or {}

        if not isinstance(parameters, dict):
            return True, ""

        if parameters.get("type") not in (None, "object"):
            return True, ""

        properties = parameters.get("properties") or {}

        if not isinstance(properties, dict):
            properties = {}

        required = parameters.get("required") or []

        if not isinstance(required, list):
            required = []

        missing = [field for field in required if field not in arguments]

        if missing:
            return (
                False,
                "Missing required argument(s): "
                + ", ".join(str(item) for item in missing),
            )

        for key, value in arguments.items():
            schema = properties.get(key)

            if not isinstance(schema, dict):
                continue

            expected_type = schema.get("type")

            if not expected_type:
                continue

            if not self._matches_type(value, expected_type):
                return (
                    False,
                    (
                        f"Invalid type for argument '{key}': "
                        f"expected {expected_type}, "
                        f"got {type(value).__name__}"
                    ),
                )

        return True, ""

    def dispatch(
        self,
        tool_call: Any,
        tool_definition: dict | None = None,
    ) -> dict:
        """
        Parse and validate a tool call.

        Returns a structured result instead of throwing for normal
        model-generated malformed calls.

        Example:
        {
            "valid": True,
            "name": "read",
            "arguments": {...},
            "id": "...",
            "type": "function",
            "error": None,
        }
        """

        try:
            name, raw_arguments, call_id, call_type = self._extract_tool_call(tool_call)
        except Exception as exc:
            self.logger.warning(f"Invalid tool call format: {exc}")

            return {
                "valid": False,
                "name": "",
                "arguments": {},
                "id": None,
                "type": "function",
                "error": str(exc),
            }

        if not name:
            self.logger.warning("Tool call is missing tool name.")

            return {
                "valid": False,
                "name": "",
                "arguments": {},
                "id": call_id,
                "type": call_type,
                "error": "Tool call is missing tool name.",
            }

        try:
            arguments = self._parse_arguments(raw_arguments)
        except Exception as exc:
            self.logger.warning(f"Invalid arguments for tool '{name}': {exc}")

            return {
                "valid": False,
                "name": name,
                "arguments": {},
                "id": call_id,
                "type": call_type,
                "error": str(exc),
            }

        parameters = None

        if isinstance(tool_definition, dict):
            function = tool_definition.get("function", {})

            if isinstance(function, dict):
                parameters = function.get("parameters")

        valid, error = self.validate(
            arguments=arguments,
            parameters=parameters,
        )

        if not valid:
            self.logger.warning(f"Tool validation failed for '{name}': {error}")

            return {
                "valid": False,
                "name": name,
                "arguments": arguments,
                "id": call_id,
                "type": call_type,
                "error": error,
            }

        return {
            "valid": True,
            "name": name,
            "arguments": arguments,
            "id": call_id,
            "type": call_type,
            "error": None,
        }
