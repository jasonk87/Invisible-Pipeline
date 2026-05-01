import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from memory_core.types import MemoryEntry


class MemoryStore:
    def __init__(self, store_dir: str | None = None, filename: str = "memories.jsonl"):
        base_dir = Path(store_dir) if store_dir is not None else Path.cwd() / "memories"
        self.path = base_dir / filename
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def remember(
        self,
        text: str,
        tags: list[str] | None = None,
        metadata: dict[str, str] | None = None,
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
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(entry), ensure_ascii=False) + "\n")
        return entry

    def list_memories(self) -> list[MemoryEntry]:
        if not self.path.exists():
            return []
        memories: list[MemoryEntry] = []
        with self.path.open("r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                memories.append(MemoryEntry(**json.loads(line)))
        return memories

    def recall(self, query: str, tags: list[str] | None = None, limit: int = 10) -> list[MemoryEntry]:
        entries = self.list_memories()
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
            haystack = " ".join([entry.text, " ".join(entry.tags), " ".join(entry.metadata.values())]).lower()
            score = sum(1 for term in query_terms if term in haystack)
            if score > 0:
                scored.append((score, idx, entry))

        scored.sort(key=lambda item: (-item[0], -item[1]))
        return [entry for _, _, entry in scored[:limit]]

    def delete_memory(self, memory_id: str) -> bool:
        entries = self.list_memories()
        kept = [e for e in entries if e.id != memory_id]
        if len(kept) == len(entries):
            return False
        with self.path.open("w", encoding="utf-8") as f:
            for entry in kept:
                f.write(json.dumps(asdict(entry), ensure_ascii=False) + "\n")
        return True


def _store_from_path(store_path: str | None) -> MemoryStore:
    if store_path is None:
        return MemoryStore()
    p = Path(store_path)
    return MemoryStore(store_dir=str(p.parent), filename=p.name)


def remember(text: str, tags: list[str] | None = None, metadata: dict[str, str] | None = None, store_path: str | None = None) -> MemoryEntry:
    return _store_from_path(store_path).remember(text=text, tags=tags, metadata=metadata)


def list_memories(store_path: str | None = None) -> list[MemoryEntry]:
    return _store_from_path(store_path).list_memories()


def recall(query: str, tags: list[str] | None = None, limit: int = 10, store_path: str | None = None) -> list[MemoryEntry]:
    return _store_from_path(store_path).recall(query=query, tags=tags, limit=limit)


def delete_memory(memory_id: str, store_path: str | None = None) -> bool:
    return _store_from_path(store_path).delete_memory(memory_id)
