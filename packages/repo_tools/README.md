# repo_tools

Small, safe, read-only project inspection toolkit.

## Install (editable)

```bash
cd packages/repo_tools
pip install -e .
```

## Usage

```python
from repo_tools import tree_summary, read_text, command_fact

facts = [
    "TREE:\n" + tree_summary("."),
    "TESTS:\n" + command_fact(["pytest", "-q"]),
]
```
