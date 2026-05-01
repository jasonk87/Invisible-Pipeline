# tool_core

Minimal object-oriented tool system for local AI agents.

## Install (editable)

```bash
cd packages/tool_core
pip install -e .
```

## Usage

```python
from tool_core import ToolRegistry
from tool_core.builtins import tree_summary_tool, read_text_tool

tools = ToolRegistry()
tools.add(tree_summary_tool())
tools.add(read_text_tool())

result = tools.call("tree_summary", {"root": "."})
```

Tools are structured objects, and failures return `ToolResult` instead of crashing.
Tool groups let agents expose many internal actions as one model-facing tool.
Write tools will come later behind workspace safety.
