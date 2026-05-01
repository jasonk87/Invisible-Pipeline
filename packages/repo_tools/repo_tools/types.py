from dataclasses import dataclass


@dataclass(slots=True)
class FileInfo:
    path: str
    size_bytes: int
