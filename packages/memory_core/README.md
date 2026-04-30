# memory_core

Minimal shared local memory module for Python projects.

## Install (editable)

```bash
cd packages/memory_core
pip install -e .
```

## Usage

```python
from memory_core import remember, recall

remember("Jason likes local Ollama models", tags=["user", "models"])
results = recall("Ollama", tags=["user"])
```
