# agent_core

Minimal object-oriented agent composition layer.

## Install (editable)

```bash
cd packages/agent_core
pip install -e .
```

## Usage

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

Agent is a composition object.
`response_mode` controls raw / think / pipeline generation.
`tools` and `workspace` are stored for future ReAct mode but not executed yet.
ReAct/tool-loop support comes later.


Agent prompts are dynamically assembled. Empty sections are omitted. Tools/workspace/memory are only included when present on the Agent. Pipeline mode still delegates to `invisible_pipeline` for now.


Agent now uses `context_core` prompt packing for all response modes (`raw`, `think`, `pipeline`). This shared packed context prevents silent truncation. If packing fails, generation returns structured errors instead of degraded output.


Agent also supports ReAct-style execution (`execution_style="react"`) with deterministic bounded loops. Tool calls must be valid JSON (`{"tool": "...", "args": {...}}`), default `max_actions` is 10, and forced final-answer fallback prevents incomplete runs.


```python
step = agent.generate("Inspect this repo")

if step.kind == "tool_call":
    result = agent.run_tool(step)
    print(result.output)
```

`generate()` decides and `run_tool()` executes, enabling approval/inspection workflows and UI-driven manual control.


ReAct mode now validates tool-call JSON before execution and retries invalid calls (bounded) without consuming action budget. If retries are exhausted, generation stops with `stop_reason="tool_validation_failed"`.
