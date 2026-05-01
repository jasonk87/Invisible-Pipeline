from dataclasses import dataclass

ALLOWED_POLICIES = {"preserve", "compact", "truncate", "drop"}


@dataclass(slots=True)
class ContextSection:
    name: str
    text: str
    policy: str
    priority: int = 50
    metadata: dict | None = None

    def __post_init__(self) -> None:
        if self.policy not in ALLOWED_POLICIES:
            raise ValueError(f"Invalid policy: {self.policy}")
