from dataclasses import dataclass


@dataclass(slots=True)
class EnvValue:
    key: str
    value: str
