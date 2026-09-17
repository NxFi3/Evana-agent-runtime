from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from src.models.ToolCall import ToolCall


class ToolDispatcher:

    def __init__(self, tool_registry):
        self.tool_registry = tool_registry

    def dispatch(
        self,
        raw_calls: Any,
    ) -> list[ToolCall]:

        if raw_calls is None:
            return []

        if isinstance(raw_calls, (dict, Mapping)):
            raw_calls = [raw_calls]

        elif not isinstance(raw_calls, (list, tuple)):
            raw_calls = [raw_calls]

        results: list[ToolCall] = []

        for raw_call in raw_calls:
            results.append(self._dispatch_call(raw_call))

        return results

    def _dispatch_call(
        self,
        raw_call: Any,
    ) -> ToolCall:

        try:

            name, arguments = self._extract_tool_call(raw_call)

            if not isinstance(name, str):
                return ToolCall(
                    name="",
                    valid=False,
                )

            name = name.strip()

            if not name:
                return ToolCall(
                    name="",
                    valid=False,
                )

            arguments = self._normalize_arguments(arguments)

            if arguments is None:
                return ToolCall(
                    name=name,
                    valid=False,
                )

            if not self.tool_registry.is_available(name):
                return ToolCall(
                    name=name,
                    args=arguments,
                    valid=False,
                )

            tool = self.tool_registry.get(name)

            if tool is None:
                return ToolCall(
                    name=name,
                    args=arguments,
                    valid=False,
                )

            validate = getattr(
                tool,
                "validate",
                None,
            )

            if callable(validate):

                try:
                    validation_result = validate(arguments)

                except Exception:
                    return ToolCall(
                        name=name,
                        args=arguments,
                        valid=False,
                    )

                if validation_result is False:
                    return ToolCall(
                        name=name,
                        args=arguments,
                        valid=False,
                    )

            return ToolCall(
                name=name,
                args=arguments,
                valid=True,
            )

        except Exception:
            return ToolCall(
                name="",
                valid=False,
            )

    @staticmethod
    def _extract_tool_call(
        raw_call: Any,
    ) -> tuple[Any, Any]:

        function = getattr(
            raw_call,
            "function",
            None,
        )

        if function is not None:

            name = getattr(
                function,
                "name",
                None,
            )

            arguments = getattr(
                function,
                "arguments",
                None,
            )

            return name, arguments

        if isinstance(
            raw_call,
            Mapping,
        ):

            # OpenAI/Ollama style:
            #
            # {
            #     "function": {
            #         "name": "...",
            #         "arguments": {...}
            #     }
            # }

            nested_function = raw_call.get("function")

            if isinstance(
                nested_function,
                Mapping,
            ):
                return (
                    nested_function.get("name"),
                    nested_function.get(
                        "arguments",
                        {},
                    ),
                )

            # Flat style:
            #
            # {
            #     "name": "...",
            #     "arguments": {...}
            # }

            return (
                raw_call.get("name"),
                raw_call.get(
                    "arguments",
                    {},
                ),
            )

        return None, None

    @staticmethod
    def _normalize_arguments(
        arguments: Any,
    ) -> dict[str, Any] | None:

        if arguments is None:
            return {}

        if isinstance(
            arguments,
            Mapping,
        ):
            return dict(arguments)

        if isinstance(
            arguments,
            str,
        ):

            arguments = arguments.strip()

            if not arguments:
                return {}

            try:
                parsed = json.loads(arguments)
            except (
                json.JSONDecodeError,
                TypeError,
            ):
                return None

            if not isinstance(
                parsed,
                Mapping,
            ):
                return None

            return dict(parsed)

        return None
