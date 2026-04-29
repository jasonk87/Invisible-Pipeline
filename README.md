<div align="center">
<img width="1200" height="475" alt="GHBanner" src="https://github.com/user-attachments/assets/0aa67016-6eaf-458a-adb2-6e31a0763ed6" />
</div>

# Run and deploy your AI Studio app

This contains everything you need to run your app locally.

View your app in AI Studio: https://ai.studio/apps/810c4d9a-8573-400e-a680-e301beec7f88

## Run Locally

**Prerequisites:**  Node.js


1. Install dependencies:
   `npm install`
2. Set the `GEMINI_API_KEY` in [.env.local](.env.local) to your Gemini API key
3. Run the app:
   `npm run dev`


## Python package usage

`invisible_pipeline` is a direct Python import for other Python projects.

```python
from invisible_pipeline import command_fact, run_pipeline

facts = [command_fact(["python", "--version"])]
result = run_pipeline("Explain this environment", facts=facts)
```

If you have a TypeScript UI, it can call this package later through a thin backend layer (for example, a minimal HTTP endpoint).

Facts are caller-provided objective evidence (lint/test/output/search results), not pipeline history.

A runnable example is included at `examples/basic_usage.py`:

```bash
python examples/basic_usage.py
```


## Real Local Usage

1. **Simple Gemini run**

```bash
python -m invisible_pipeline "Explain the difference between unit tests and integration tests."
```

2. **Simple Ollama run (long timeout)**

```bash
python -m invisible_pipeline   --model ollama:llama3.2   --timeout 600   "Draft a concise release checklist for a Python library."
```

3. **Code/test fact run**

```bash
python -m invisible_pipeline   --fact-command "pytest -q"   "Given the test output fact, summarize project test health and likely next steps."
```

Fact commands are external evidence only; they are not automatic tool loops and do not give the pipeline memory.
