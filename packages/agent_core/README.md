# agent_core

Minimal object-oriented agent composition layer.

## Install (editable)

```bash
cd packages/agent_core
pip install -e .
```

## Usage

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

Agent is a composition object.
`response_mode` controls raw / think / pipeline generation.
`tools` and `workspace` are stored for future ReAct mode but not executed yet.
ReAct/tool-loop support comes later.


Agent prompts are dynamically assembled. Empty sections are omitted. Tools/workspace/memory are only included when present on the Agent. Pipeline mode still delegates to `invisible_pipeline` for now.


Agent now uses `context_core` prompt packing for all response modes (`raw`, `think`, `pipeline`). This shared packed context prevents silent truncation. If packing fails, generation returns structured errors instead of degraded output.


Agent also supports ReAct-style execution (`execution_mode="react"`) with deterministic bounded loops. Tool calls must be valid JSON (`{"tool": "...", "args": {...}}`), default `max_actions` is 10, and forced final-answer fallback prevents incomplete runs.


```python
step = agent.generate("Inspect this repo")

if step.kind == "tool_call":
    result = agent.run_tool(step)
    print(result.output)
```

`generate()` decides and `run_tool()` executes, enabling approval/inspection workflows and UI-driven manual control.


ReAct mode now validates tool-call JSON before execution and retries invalid calls (bounded) without consuming action budget. If retries are exhausted, generation stops with `stop_reason="tool_validation_failed"`.


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


`llm_core` handles raw model calls. `agent_core` handles identity/behavior/tools/teams.

```python
from llm_core import LLMClient
from agent_core import Agent

llm = LLMClient(model="ollama:gemma:e2b", timeout=600)

agent = Agent(
    name="assistant",
    llm=llm,
    response_mode="pipeline",
)

result = agent.generate("Explain this project.")
print(result.text)
```

`generate_fn` remains supported for lightweight injection/testing.


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
