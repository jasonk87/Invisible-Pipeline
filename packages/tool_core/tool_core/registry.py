from tool_core.types import Tool, ToolResult


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def add(self, tool: Tool):
        if tool.name in self._tools:
            raise ValueError(f"Duplicate tool name: {tool.name}")
        self._tools[tool.name] = tool

    def remove(self, name: str):
        self._tools.pop(name, None)

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def call(self, name: str, args: dict) -> ToolResult:
        tool = self.get(name)
        if tool is None:
            return ToolResult(ok=False, error=f"Tool not found: {name}")
        return tool.call(args)

    def list_tools(self) -> list[Tool]:
        return list(self._tools.values())

    def list_specs(self) -> list[dict]:
        return [
            {
                "name": t.name,
                "description": t.description,
                "parameters": t.parameters,
                "risk": t.risk,
            }
            for t in self.list_tools()
        ]
