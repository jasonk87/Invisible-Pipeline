from dataclasses import dataclass


@dataclass(slots=True)
class AgentResult:
    text: str
    completed: bool = True
    stop_reason: str = "final_answer"
    metadata: dict | None = None


@dataclass(slots=True)
class AgentStep:
    kind: str
    text: str = ""
    tool_name: str | None = None
    tool_args: dict | None = None
    metadata: dict | None = None


@dataclass(slots=True)
class ToolValidationResult:
    ok: bool
    errors: list[str]
