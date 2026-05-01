# Local AI Modules Workspace

This repository is organized as a workspace with reusable Python modules and app UIs separated.

## Workspace layout

- `packages/invisible_pipeline/` — reusable Python package
  - `invisible_pipeline/` — package source
  - `tests/` — Python tests
  - `examples/` — runnable examples
  - `pyproject.toml` — editable install metadata
- `packages/model_router/` — shared minimal model access package
- `apps/module_lab_ui/` — React/Vite UI application

## Install the Python package (editable)

```bash
cd packages/invisible_pipeline
pip install -e .
```

Then in Python:

```python
from invisible_pipeline import run_pipeline, command_fact, list_ollama_models
```

## Run Python tests

```bash
cd packages/invisible_pipeline
python -m unittest discover -s tests -p 'test_*.py'
```

## Run the UI app

```bash
cd apps/module_lab_ui
npm install
npm run dev
```


## Install model_router (editable)

```bash
cd packages/model_router
pip install -e .
```

```python
from model_router import generate, list_models
```


## Using model_router with invisible_pipeline

You can inject `model_router.generate` into `invisible_pipeline.run_pipeline` via `generate_fn`.
This keeps the packages separate and avoids a hard dependency between them.

Example:

```python
from invisible_pipeline import run_pipeline
from model_router import generate

result = run_pipeline(
    task="Explain the cleanest architecture for a small AI assistant.",
    model="ollama:gemma:e2b",
    max_rounds=4,
    timeout=600,
    generate_fn=generate,
)

print(result.final_answer)
```

Runnable script: `examples/pipeline_with_model_router.py`


## Install memory_core (editable)

```bash
cd packages/memory_core
pip install -e .
```

```python
from memory_core import MemoryStore

memory = MemoryStore()
memory.remember("Jason likes local Ollama models", tags=["user", "models"])
results = memory.recall("Ollama", tags=["user"])
```


## memory_core + invisible_pipeline integration

`memory_core` does not depend on `invisible_pipeline`, and `invisible_pipeline` does not depend on `memory_core`.
Integration happens at the call site by turning recalled memories into facts and passing them into `run_pipeline(...)`.

See: `examples/memory_pipeline_example.py`


`MemoryStore()` defaults to `./memories/memories.jsonl` relative to the current working directory.


## Install repo_tools (editable)

```bash
cd packages/repo_tools
pip install -e .
```

```python
from repo_tools import tree_summary, read_text, command_fact

facts = [
    "TREE:\n" + tree_summary("."),
    "TESTS:\n" + command_fact(["pytest", "-q"]),
]
```


## Install context_core (editable)

```bash
cd packages/context_core
pip install -e .
```

```python
from context_core import ContextBuilder
from model_router import generate

ctx = ContextBuilder(model="ollama:gemma:e2b", generate_fn=generate)

ctx.add("system_rules", rules, policy="preserve")
ctx.add("tools", tool_specs, policy="preserve")
ctx.add("chat", chat_log, policy="compact")

result = ctx.pack(task)

if not result.ok:
    print(result.errors)
else:
    print(result.text)
```


`context_core` context window defaults are estimates; callers can override `context_window`, and effective usable context is still limited by `max_usage_ratio`.


## Install tool_core (editable)

```bash
cd packages/tool_core
pip install -e .
```

```python
from tool_core import ToolRegistry
from tool_core.builtins import tree_summary_tool, read_text_tool

tools = ToolRegistry()
tools.add(tree_summary_tool())
tools.add(read_text_tool())

result = tools.call("tree_summary", {"root": "."})
```

Tools are structured objects, tool failures return `ToolResult` instead of crashing, and tool groups let many internal actions be exposed as one model-facing tool. Write tools will come later behind workspace safety.


## Install workspace_core (editable)

```bash
cd packages/workspace_core
pip install -e .
```

```python
from workspace_core import Workspace

ws = Workspace(root=".", read_only=True)
text = ws.read_text("src/main.py")
```

Workspace enforces safe boundaries for tools. All file tools should go through `Workspace`, and write operations require `read_only=False`.


### Workspace-backed file tools (tool_core)

```python
from workspace_core import Workspace
from tool_core import ToolRegistry
from tool_core.builtins import read_file_tool, write_file_tool, apply_patch_tool

ws = Workspace(root=".", read_only=False)

tools = ToolRegistry()
tools.add(read_file_tool(ws))
tools.add(write_file_tool(ws))
tools.add(apply_patch_tool(ws))

result = tools.call("apply_patch", {
    "path": "src/main.py",
    "search": "old text",
    "replace": "new text",
    "dry_run": True,
    "match_mode": "exact",
})
```

Write tools require `Workspace`. `apply_patch` defaults to `dry_run=True`, and ambiguous patches fail instead of guessing.


## Install agent_core (editable)

```bash
cd packages/agent_core
pip install -e .
```

```python
from agent_core import Agent

agent = Agent(
    model="ollama:gemma:e2b",
    response_mode="pipeline",
    max_rounds=4,
)

result = agent.generate("Explain the cleanest architecture for this project.")
print(result.text)
```

Agent is a composition object, `response_mode` controls raw/think/pipeline generation, and `tools`/`workspace` are stored for future ReAct mode but not executed yet. ReAct/tool-loop support comes later.


Agent prompts are dynamically assembled; empty sections are omitted, and tools/workspace/memory context is only included when the Agent has those components. Pipeline mode still delegates to `invisible_pipeline` for now.


`agent_core` now applies `context_core` packing before all response modes, so raw/think/pipeline share identical packed input. Context packing failures return structured errors instead of silently degrading output.


`agent_core` now supports ReAct-style execution with deterministic bounded loops (`max_actions=10` by default). Tool calls must be valid JSON, and forced final-answer fallback prevents incomplete runs.


```python
step = agent.generate("Inspect this repo")

if step.kind == "tool_call":
    result = agent.run_tool(step)
    print(result.output)
```

`generate()` decides and `run_tool()` executes, enabling approval/inspection workflows and UI-driven manual control.


ReAct mode now validates tool-call JSON before execution and retries invalid calls (bounded) without consuming action budget. If retries are exhausted, generation stops with `stop_reason="tool_validation_failed"`.


### Full ReAct workspace example

```bash
python examples/react_workspace_agent_example.py
```

This example wires together `Agent`, `Workspace`, `ToolRegistry`, and `model_router`. ReAct mode can call registered tools, `max_actions` defaults to 10 (shown explicitly for clarity), tool calls are validated before execution, invalid tool calls trigger strict correction before retry, and `Workspace` enforces file boundaries.
