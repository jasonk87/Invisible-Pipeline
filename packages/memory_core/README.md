# memory_core

Minimal shared local memory module for Python projects.

## Install (editable)

```bash
cd packages/memory_core
pip install -e .
```

## Usage (project-local storage)

```python
from memory_core import MemoryStore

memory = MemoryStore()
memory.remember("Jason prefers local Ollama models", tags=["user"])
results = memory.recall("Ollama")
```

`MemoryStore()` defaults to `./memories/memories.jsonl` relative to the current working directory.

Top-level compatibility functions are also available:

```python
from memory_core import remember, recall

remember("Jason likes local Ollama models", tags=["user", "models"])
results = recall("Ollama", tags=["user"])
```
