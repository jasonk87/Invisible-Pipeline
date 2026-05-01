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
from agent_core import Agent, AgentTeam

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


ReAct mode now returns execution events in `result.metadata["events"]` for debugging/UI display. This is not streaming yet; streaming can be layered on top later.

```python
result = agent.generate("Inspect this project")

for event in result.metadata.get("events", []):
    print(event["title"])
```


## AgentTeam (Phase 1)

```python
team = AgentTeam(
    agents=[planner, coder, reviewer],
    team_mode="round_robin",
    completion_policy="reviewed",
    human_member=False,
    expose_tool_activity=True,
    max_turns=10,
)

result = team.run("Design a simple snake game")
print(result.text)
```

Phase 1 supports deterministic round-robin coordination only (no moderator/orchestrator mode yet).

Completion policies:
- `single_done`: first standalone `DONE` ends the run immediately.
- `reviewed` (default): one standalone `DONE` must be confirmed by the next round-robin agent with standalone `DONE`.
- `all_members`: each current agent must emit standalone `DONE` at least once.
- `supervised`: owner-controlled completion. Use `human_member="proxy"` and an agent named `human_proxy` to emit standalone `DONE`. With `human_member=True`, real human turns are reserved for future implementation, so auto-completion is disabled in Phase 1.

`DONE` is recognized only when the entire response is exactly `DONE` (case-insensitive, surrounding whitespace ignored).

`TEAM TRANSCRIPT` contains what agents said. `TEAM ACTIVITY` contains compact summaries of what agents did based on agent events (`tool_call`, `observation`, `validation_error`, `error`). Tool activity is included by default; set `expose_tool_activity=False` to disable it in prompts.


## AgentTeam Example (Round Robin)

In Phase 1, agents take turns in fixed order (round robin). The transcript is shared context, each agent builds on prior responses, the final answer comes from the first agent that completes, and `max_turns` provides a deterministic stop.

```bash
python examples/agent_team_round_robin_example.py
```


## Team Sessions

`run()` is a one-shot convenience wrapper. For persistent workflows, create a session explicitly:

```python
session = team.create_session("Build a snake game")
session.run()

session.continue_run("Add scoring and restart button")

session.restart()
session.run()
```

Sessions preserve transcript and activity across continued runs, maintain task history, and keep a stable session id. Each session is isolated from other sessions on the same `AgentTeam`.

`restart()` reuses the same session object/session id while clearing prior transcript/activity/events and run state. `continue_run()` preserves prior history, while `restart()` wipes it.


## llm_core

Install:

```bash
cd packages/llm_core
pip install -e .
```

Usage:

```python
from llm_core import LLMClient

llm = LLMClient(model="ollama:gemma:e2b", timeout=600)
result = llm.generate("Explain ECS clearly.")
print(result.text)
```

`llm_core` is for raw model calls only. `agent_core` is for identity, behavior, tools, and teams. Use `LLMClient` anywhere a plain model call is needed.


Agent identity fields:

```python
from llm_core import LLMClient
from agent_core import Agent

llm = LLMClient(model="ollama:gemma:e2b", timeout=600)

agent = Agent(
    name="builder",
    role="Writes clean implementation code.",
    persona="Practical, concise, avoids overengineering.",
    llm=llm,
)
```

`LLMClient` is identity-free raw model calling. `Agent` adds identity + behavior. If role is omitted it defaults to `General assistant`; persona is optional. Team prompts include member identity so each agent sees roles/personas during coordination.


## prompt_core

`prompt_core` standardizes prompt text formatting. It does not call models or execute tools. `agent_core` can use `prompt_core` when available, and `context_core` can pack its output before model calls. It now includes stronger grounded default agent instructions, team instructions that discourage repetition/premature DONE, and stricter JSON-only tool correction instructions.

Install:

```bash
cd packages/prompt_core
pip install -e .
```

```python
from prompt_core import build_agent_prompt

prompt = build_agent_prompt(
    task="Review this project",
    agent_name="reviewer",
    agent_role="Find correctness issues.",
    facts=["pytest failed"],
)
```


## env_core

`packages/env_core/env/.env` is the shared module-owned environment file for local AI modules.

Example values:

```env
GEMINI_API_KEY=your_key_here
GOOGLE_SEARCH_API_KEY=your_key_here
GOOGLE_SEARCH_ENGINE_ID=your_engine_id_here
```

- Individual projects do not need their own `.env`.
- Modules that need keys should call `env_core` internally.
- `packages/env_core/env/.env` is gitignored.
- `packages/env_core/env/.env.example` is committed.


Orchestrator mode (Phase 1 dynamic routing):

```python
manager = Agent(name="manager", role="Routes work to the right team member.")

team = AgentTeam(
    agents=[planner, builder, reviewer],
    team_mode="orchestrator",
    orchestrator=manager,
    max_turns=10,
)
```

In orchestrator mode, the orchestrator must return strict JSON to select the next speaker (or finish). Routing guidance emphasizes task state, prior/missing work, and each member's role/persona to reduce repetition and premature completion. Completion policies are not applied inside orchestrator mode in Phase 1; completion comes from orchestrator `{"done": true, "final_answer": "..."}`. Round-robin remains the default mode.


### tool_core optional web built-ins

```python
from tool_core import ToolRegistry
from tool_core.builtins import web_search_tool, fetch_url_tool

tools = ToolRegistry()
tools.add(web_search_tool())
tools.add(fetch_url_tool())
```

Required in `packages/env_core/env/.env`:

```env
GOOGLE_SEARCH_API_KEY=...
GOOGLE_SEARCH_ENGINE_ID=...
```

Web tools are optional built-ins, only called when registered, and use `env_core` lazily.


## Observability / Tracing

- Enable LLM tracing with `LLMClient(enable_tracing=True)`.
- Built-in tools now include timing/args metadata in `ToolResult.metadata`.
- `TeamSession` aggregates per-agent traces into `TeamResult.metadata["llm_traces"]` and `TeamResult.metadata["tool_traces"]`.

```python
llm = LLMClient(enable_tracing=True)
agent = Agent(name="builder", llm=llm)
team = AgentTeam(agents=[agent])
result = team.run("task")
print(result.metadata["llm_traces"])
print(result.metadata["tool_traces"])
```


### Debug Viewer

```python
import json

result = session.run()

with open("debug.json", "w", encoding="utf-8") as f:
    json.dump(result.metadata, f, default=str, indent=2)
```

```bash
python -m agent_core.debug_viewer debug.json
```

The viewer is for post-run inspection (not streaming) and helps inspect prompts/responses/tool calls/events.


## Module Lab (UI + local backend)

Backend:

```bash
cd apps/module_lab_server
python -m uvicorn main:app --reload --port 5000
```

Frontend:

```bash
cd apps/module_lab_ui
npm install
npm run dev
```

The frontend should call `http://localhost:5000`.
