from src.Tools.ToolRegistry import ToolRegistry 




registry = ToolRegistry()

tools = registry.discovery()

print("\nDiscovered tools:")

for tool in tools:
    print(
        f"- {tool.name} -> {tool}"
    )

