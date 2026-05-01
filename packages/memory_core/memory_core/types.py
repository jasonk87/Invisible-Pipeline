from dataclasses import dataclass


@dataclass(slots=True)
class MemoryEntry:
    id: str
    text: str
    tags: list[str]
    created_at: str
    metadata: dict[str, str]
