from dataclasses import dataclass


@dataclass(slots=True)
class LLMResult:
    text: str
    model: str
    metadata: dict | None = None
