from dataclasses import dataclass


@dataclass(slots=True)
class ContextPackResult:
    ok: bool
    text: str
    estimated_tokens: int
    max_tokens: int
    warnings: list[str]
    errors: list[str]
    compacted_sections: list[str]
    dropped_sections: list[str]
