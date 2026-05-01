# workspace_core

Strict workspace filesystem boundary enforcement.

## Install (editable)

```bash
cd packages/workspace_core
pip install -e .
```

## Usage

```python
from workspace_core import Workspace

ws = Workspace(root=".", read_only=True)
text = ws.read_text("src/main.py")
```

Workspace enforces safe boundaries for tools.
All file tools should go through `Workspace`.
Write operations require `read_only=False`.
