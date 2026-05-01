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
