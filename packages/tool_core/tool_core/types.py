from dataclasses import dataclass
from typing import Callable


@dataclass(slots=True)
class ToolResult:
    ok: bool
    output: str = ""
    error: str | None = None
    metadata: dict | None = None


class Tool:
    def __init__(self, name: str, description: str, parameters: dict, handler: Callable[..., ToolResult], risk: str = "safe"):
        if not name.strip():
            raise ValueError("Tool name must be non-empty")
        if risk not in {"safe", "write", "dangerous"}:
            raise ValueError("Invalid risk level")
        self.name = name
        self.description = description
        self.parameters = parameters
        self.handler = handler
        self.risk = risk

    def call(self, args: dict) -> ToolResult:
        try:
            result = self.handler(**args)
            if isinstance(result, ToolResult):
                return result
            return ToolResult(ok=True, output=str(result))
        except Exception as exc:
            return ToolResult(ok=False, error=str(exc))
