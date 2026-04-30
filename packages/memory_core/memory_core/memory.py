import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from memory_core.types import MemoryEntry

DEFAULT_STORE_PATH = "~/.ai_modules/memory_core/memories.jsonl"


def _resolve_store_path(store_path: str | None) -> Path:
    return Path(store_path or DEFAULT_STORE_PATH).expanduser()


def remember(
    text: str,
    tags: list[str] | None = None,
    metadata: dict[str, str] | None = None,
    store_path: str | None = None,
) -> MemoryEntry:
    if not text.strip():
        raise ValueError("text must be non-empty")

    entry = MemoryEntry(
        id=str(uuid4()),
        text=text,
        tags=list(tags or []),
        created_at=datetime.now(timezone.utc).isoformat(),
        metadata=dict(metadata or {}),
    )

    path = _resolve_store_path(store_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(asdict(entry), ensure_ascii=False) + "\n")
    return entry


def list_memories(store_path: str | None = None) -> list[MemoryEntry]:
    path = _resolve_store_path(store_path)
    if not path.exists():
        return []

    memories: list[MemoryEntry] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            obj = json.loads(line)
            memories.append(MemoryEntry(**obj))
    return memories


def recall(
    query: str,
    tags: list[str] | None = None,
    limit: int = 10,
    store_path: str | None = None,
) -> list[MemoryEntry]:
    entries = list_memories(store_path)
    if limit <= 0:
        return []

    required_tags = set(tags or [])
    if required_tags:
        entries = [e for e in entries if required_tags.issubset(set(e.tags))]

    if not query.strip():
        return list(reversed(entries))[:limit] if required_tags else []

    query_terms = [t for t in query.lower().split() if t]
    scored: list[tuple[int, int, MemoryEntry]] = []

    for idx, entry in enumerate(entries):
        haystack = " ".join(
            [
                entry.text,
                " ".join(entry.tags),
                " ".join(entry.metadata.values()),
            ]
        ).lower()
        score = sum(1 for term in query_terms if term in haystack)
        if score > 0:
            scored.append((score, idx, entry))

    scored.sort(key=lambda item: (-item[0], -item[1]))
    return [entry for _, _, entry in scored[:limit]]


def delete_memory(memory_id: str, store_path: str | None = None) -> bool:
    path = _resolve_store_path(store_path)
    entries = list_memories(store_path)
    kept = [e for e in entries if e.id != memory_id]
    if len(kept) == len(entries):
        return False

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for entry in kept:
            f.write(json.dumps(asdict(entry), ensure_ascii=False) + "\n")
    return True
