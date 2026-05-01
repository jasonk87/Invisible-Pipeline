from agent_core import Agent
from model_router import generate
from tool_core import ToolRegistry
from tool_core.builtins import (
    append_file_tool,
    apply_patch_tool,
    command_fact_tool,
    read_file_tool,
    tree_summary_tool,
    write_file_tool,
)
from workspace_core import Workspace

# This example enables write-capable tools because read_only=False.
# apply_patch_tool defaults to dry_run=True, but write operations are still possible.
# Use read_only=True for safer inspection-only mode.
workspace = Workspace(root=".", read_only=False)

tools = ToolRegistry()
tools.add(read_file_tool(workspace))
tools.add(write_file_tool(workspace))
tools.add(append_file_tool(workspace))
tools.add(apply_patch_tool(workspace))
tools.add(tree_summary_tool())
tools.add(command_fact_tool())

agent = Agent(
    name="workspace_react_agent",
    model="ollama:gemma:e2b",
    response_mode="pipeline",
    execution_mode="react",
    max_actions=10,
    timeout=600,
    tools=tools,
    workspace=workspace,
    generate_fn=generate,
)

result = agent.generate(
    "Inspect this workspace and recommend the single highest-value next cleanup. "
    "Use tools if needed, but do not modify files unless there is a clear reason."
)

print(result.text)
print(f"completed={result.completed}")
print(f"stop_reason={result.stop_reason}")
print(f"metadata={result.metadata}")
