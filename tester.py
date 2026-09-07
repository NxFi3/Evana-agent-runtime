
from src.Tools.ToolRegistry import ToolRegistry
from src.Tools.Tool import Tool


passed = 0
failed = 0


def test(name, condition):
    global passed, failed

    if condition:
        print(f"[PASS] {name}")
        passed += 1
    else:
        print(f"[FAIL] {name}")
        failed += 1


print("=" * 60)
print("ToolRegistry Test")
print("=" * 60)


# ---------------------------------------------------------
# 1. Initialization
# ---------------------------------------------------------

registry = ToolRegistry()

test(
    "registry initializes",
    registry is not None
)

test(
    "tools starts empty",
    isinstance(registry.tools, dict) and len(registry.tools) == 0
)


# ---------------------------------------------------------
# 2. Discovery
# ---------------------------------------------------------

registry.discover()

test(
    "read_file discovered",
    registry.is_available("read_file")
)

test(
    "at least one tool discovered",
    len(registry.tools) >= 1
)


# ---------------------------------------------------------
# 3. Tool instances
# ---------------------------------------------------------

read_file = registry.get("read_file")

test(
    "get existing tool",
    read_file is not None
)

test(
    "existing tool is a Tool instance",
    isinstance(read_file, Tool)
)

test(
    "tool name is correct",
    read_file.name == "read_file"
)

test(
    "tool has description",
    isinstance(read_file.description, str)
    and len(read_file.description) > 0
)

test(
    "tool has parameters",
    isinstance(read_file.parameters, dict)
)


# ---------------------------------------------------------
# 4. is_available()
# ---------------------------------------------------------

test(
    "is_available returns True for existing tool",
    registry.is_available("read_file") is True
)

test(
    "is_available returns False for missing tool",
    registry.is_available("does_not_exist") is False
)


# ---------------------------------------------------------
# 5. get()
# ---------------------------------------------------------

test(
    "get returns None for missing tool",
    registry.get("does_not_exist") is None
)

test(
    "get returns same registered instance",
    registry.get("read_file") is read_file
)


# ---------------------------------------------------------
# 6. get_definitions()
# ---------------------------------------------------------

definitions = registry.get_definitions()

test(
    "get_definitions returns a list",
    isinstance(definitions, list)
)

test(
    "definitions count matches registered tools",
    len(definitions) == len(registry.tools)
)

test(
    "at least one definition exists",
    len(definitions) >= 1
)


# ---------------------------------------------------------
# 7. Validate every definition
# ---------------------------------------------------------

for definition in definitions:

    test(
        "definition is a dictionary",
        isinstance(definition, dict)
    )

    test(
        "definition type is function",
        definition.get("type") == "function"
    )

    function = definition.get("function")

    test(
        "definition contains function object",
        isinstance(function, dict)
    )

    test(
        "function has name",
        isinstance(function.get("name"), str)
        and len(function.get("name")) > 0
    )

    test(
        "function has description",
        isinstance(function.get("description"), str)
        and len(function.get("description")) > 0
    )

    test(
        "function has parameters",
        isinstance(function.get("parameters"), dict)
    )


# ---------------------------------------------------------
# 8. Registry / Definition consistency
# ---------------------------------------------------------

registered_names = set(registry.tools.keys())

definition_names = {
    definition["function"]["name"]
    for definition in definitions
}

test(
    "registered tool names match definition names",
    registered_names == definition_names
)


# ---------------------------------------------------------
# 9. Print discovered tools
# ---------------------------------------------------------

print()
print("Discovered tools:")

for tool_name, tool in registry.tools.items():
    print(f"- {tool_name} -> {tool}")


# ---------------------------------------------------------
# 10. Print definitions
# ---------------------------------------------------------

print()
print("Tool definitions:")

for definition in definitions:
    print(definition)


# ---------------------------------------------------------
# Final result
# ---------------------------------------------------------

print()
print("=" * 60)
print(f"Tests passed: {passed}")
print(f"Tests failed: {failed}")
print("=" * 60)

if failed == 0:
    print("ALL TOOL REGISTRY TESTS PASSED")
else:
    print("SOME TOOL REGISTRY TESTS FAILED")
    raise SystemExit(1)

