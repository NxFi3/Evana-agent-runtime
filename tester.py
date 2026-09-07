from pathlib import Path
from tempfile import TemporaryDirectory

from src.Tools.ToolRegistry import ToolRegistry
from src.Tools.Tool import Tool
from src.Tools.ToolResult import ToolResult


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
print("Create Tool Test")
print("=" * 60)


# ---------------------------------------------------------
# 1. Registry / Discovery
# ---------------------------------------------------------

registry = ToolRegistry()

test(
    "registry initializes",
    registry is not None
)

test(
    "tools starts empty",
    isinstance(registry.tools, dict)
    and len(registry.tools) == 0
)

registry.discover()

test(
    "create tool discovered",
    registry.is_available("create")
)

create = registry.get("create")

test(
    "get create tool",
    create is not None
)

test(
    "create is a Tool instance",
    isinstance(create, Tool)
)

test(
    "create tool name is correct",
    create.name == "create"
)


# ---------------------------------------------------------
# 2. Tool Definition
# ---------------------------------------------------------

definitions = registry.get_definitions()

create_definition = next(
    (
        definition
        for definition in definitions
        if definition["function"]["name"] == "create"
    ),
    None
)

test(
    "create definition exists",
    create_definition is not None
)

if create_definition is not None:

    test(
        "definition type is function",
        create_definition.get("type") == "function"
    )

    function = create_definition.get("function")

    test(
        "function definition exists",
        isinstance(function, dict)
    )

    if isinstance(function, dict):

        test(
            "function has name",
            function.get("name") == "create"
        )

        test(
            "function has description",
            isinstance(function.get("description"), str)
            and len(function.get("description")) > 0
        )

        parameters = function.get("parameters")

        test(
            "create has parameters",
            isinstance(parameters, dict)
        )

        if isinstance(parameters, dict):

            properties = parameters.get("properties", {})

            test(
                "file_path parameter exists",
                "file_path" in properties
            )

            test(
                "content parameter exists",
                "content" in properties
            )

            required = parameters.get("required", [])

            test(
                "file_path is required",
                "file_path" in required
            )

            test(
                "content is required",
                "content" in required
            )


# ---------------------------------------------------------
# 3. Create File
# ---------------------------------------------------------

with TemporaryDirectory() as temp_dir:

    file_path = Path(temp_dir) / "test.py"

    content = (
        "def hello():\n"
        "    print('hello')\n"
    )

    result = create.execute(
        file_path=str(file_path),
        content=content
    )

    test(
        "create returns ToolResult",
        isinstance(result, ToolResult)
    )

    test(
        "create succeeds",
        result.success is True
    )

    test(
        "created file exists",
        file_path.is_file()
    )

    test(
        "created file contains correct content",
        file_path.read_text(encoding="utf-8") == content
    )


# ---------------------------------------------------------
# 4. Existing File Protection
# ---------------------------------------------------------

with TemporaryDirectory() as temp_dir:

    file_path = Path(temp_dir) / "existing.py"

    original_content = "original content\n"

    file_path.write_text(
        original_content,
        encoding="utf-8"
    )

    result = create.execute(
        file_path=str(file_path),
        content="new content\n"
    )

    test(
        "create fails when file already exists",
        result.success is False
    )

    test(
        "existing file content is preserved",
        file_path.read_text(encoding="utf-8")
        == original_content
    )


# ---------------------------------------------------------
# 5. Nested Directory Creation
# ---------------------------------------------------------

with TemporaryDirectory() as temp_dir:

    file_path = (
        Path(temp_dir)
        / "src"
        / "utils"
        / "test.py"
    )

    content = "print('nested')\n"

    result = create.execute(
        file_path=str(file_path),
        content=content
    )

    test(
        "create succeeds in nested path",
        result.success is True
    )

    test(
        "parent directories are created",
        file_path.parent.is_dir()
    )

    test(
        "nested file exists",
        file_path.is_file()
    )

    test(
        "nested file contains correct content",
        file_path.read_text(encoding="utf-8") == content
    )


# ---------------------------------------------------------
# 6. Empty Content
# ---------------------------------------------------------

with TemporaryDirectory() as temp_dir:

    file_path = Path(temp_dir) / "empty.py"

    result = create.execute(
        file_path=str(file_path),
        content=""
    )

    test(
        "create allows empty content",
        result.success is True
    )

    test(
        "empty file is created",
        file_path.is_file()
    )

    test(
        "empty file has zero bytes",
        file_path.stat().st_size == 0
    )


# ---------------------------------------------------------
# 7. Different File Types
# ---------------------------------------------------------

with TemporaryDirectory() as temp_dir:

    files = {
        "test.txt": "hello world\n",
        "data.json": '{"name": "Evana"}\n',
        "config.yaml": "model: gpt-oss\n",
    }

    for filename, content in files.items():

        file_path = Path(temp_dir) / filename

        result = create.execute(
            file_path=str(file_path),
            content=content
        )

        test(
            f"create {filename}",
            result.success is True
        )

        test(
            f"{filename} exists",
            file_path.is_file()
        )

        test(
            f"{filename} content is correct",
            file_path.read_text(encoding="utf-8") == content
        )


# ---------------------------------------------------------
# 8. Unicode Content
# ---------------------------------------------------------

with TemporaryDirectory() as temp_dir:

    file_path = Path(temp_dir) / "unicode.txt"

    content = "Evana\nسلام دنیا\nこんにちは\n"

    result = create.execute(
        file_path=str(file_path),
        content=content
    )

    test(
        "create handles unicode content",
        result.success is True
    )

    test(
        "unicode content is preserved",
        file_path.read_text(encoding="utf-8") == content
    )


# ---------------------------------------------------------
# 9. Empty Path
# ---------------------------------------------------------

result = create.execute(
    file_path="",
    content="test"
)

test(
    "empty path fails",
    result.success is False
)


# ---------------------------------------------------------
# 10. Tool Result
# ---------------------------------------------------------

with TemporaryDirectory() as temp_dir:

    file_path = Path(temp_dir) / "result.py"

    result = create.execute(
        file_path=str(file_path),
        content="print('test')\n"
    )

    test(
        "result has success field",
        isinstance(result.success, bool)
    )

    test(
        "successful result has content",
        isinstance(result.content, str)
        and len(result.content) > 0
    )


# ---------------------------------------------------------
# Final Result
# ---------------------------------------------------------

print()
print("=" * 60)
print(f"Tests passed: {passed}")
print(f"Tests failed: {failed}")
print("=" * 60)

if failed == 0:
    print("ALL CREATE TOOL TESTS PASSED")
else:
    print("SOME CREATE TOOL TESTS FAILED")
    raise SystemExit(1)