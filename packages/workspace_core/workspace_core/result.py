from dataclasses import dataclass


@dataclass(slots=True)
class PathResult:
    ok: bool
    path: str | None
    error: str | None
