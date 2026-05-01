# context_core

Strict, section-aware context management to prevent silent truncation bugs.

Each section declares how it may be handled (`preserve`, `compact`, `truncate`, `drop`).
If required context cannot fit, `context_core` returns a failure result instead of silently cutting important data.

## Install (editable)

```bash
cd packages/context_core
pip install -e .
```

## Usage

```python
from context_core import ContextBuilder
from model_router import generate

ctx = ContextBuilder(model="ollama:gemma:e2b", generate_fn=generate)

ctx.add("system_rules", "...", policy="preserve")
ctx.add("tools", "...", policy="preserve")
ctx.add("chat", "...", policy="compact")

result = ctx.pack("your task")

if not result.ok:
    print(result.errors)
else:
    print(result.text)
```


Context window defaults are estimates. You can override `context_window` explicitly in `ContextBuilder(...)`, and max usable context remains controlled by `max_usage_ratio`.
