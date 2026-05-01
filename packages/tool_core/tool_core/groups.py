from tool_core.types import Tool, ToolResult


class ToolGroup:
    def __init__(self, name: str, description: str, actions: dict[str, Tool]):
        self.name = name
        self.description = description
        self.actions = actions

    def call(self, args: dict) -> ToolResult:
        action = args.get("action")
        if not action:
            return ToolResult(ok=False, error="Missing action")
        tool = self.actions.get(action)
        if tool is None:
            return ToolResult(ok=False, error=f"Unknown action: {action}")
        payload = {k: v for k, v in args.items() if k != "action"}
        return tool.call(payload)

    def list_spec(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": sorted(self.actions.keys())}
                },
                "required": ["action"],
            },
            "risk": "safe",
        }
