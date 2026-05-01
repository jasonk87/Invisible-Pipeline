from dataclasses import dataclass


@dataclass(slots=True)
class LLMResult:
    text: str
    model: str
    metadata: dict | None = None


@dataclass(slots=True)
class LLMCallRecord:
    id: str
    model: str
    prompt: str
    response: str | None
    started_at: float
    ended_at: float
    duration_ms: int
    error: str | None
    metadata: dict | None = None
