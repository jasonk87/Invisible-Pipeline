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
from memory_core import remember, recall

remember("Jason likes local Ollama models", tags=["user", "models"])
results = recall("Ollama", tags=["user"])
```


## memory_core + invisible_pipeline integration

`memory_core` does not depend on `invisible_pipeline`, and `invisible_pipeline` does not depend on `memory_core`.
Integration happens at the call site by turning recalled memories into facts and passing them into `run_pipeline(...)`.

See: `examples/memory_pipeline_example.py`
