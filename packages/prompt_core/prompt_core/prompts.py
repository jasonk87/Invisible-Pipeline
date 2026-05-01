from prompt_core.sections import PromptSection


def build_prompt(sections: list[PromptSection], instruction: str | None = None) -> str:
    blocks = []
    for section in sections:
        if not section.content:
            continue
        blocks.append(f"{section.title}:\n{section.content}")
    if instruction:
        blocks.append(f"INSTRUCTION:\n{instruction}")
    return "\n\n".join(blocks)


def build_agent_prompt(task: str, agent_name: str | None = None, agent_role: str | None = None, agent_persona: str | None = None, facts: list[str] | None = None, tools_text: str | None = None, workspace_text: str | None = None, memory_text: str | None = None, instruction: str | None = None) -> str:
    identity = []
    if agent_name:
        identity.append(f"Name: {agent_name}")
    if agent_role:
        identity.append(f"Role: {agent_role}")
    if agent_persona:
        identity.append(f"Persona: {agent_persona}")
    facts_text = "\n".join(f"- {fact}" for fact in (facts or []))
    sections = [
        PromptSection("AGENT", "\n".join(identity)),
        PromptSection("TASK", task),
        PromptSection("FACTS", facts_text),
        PromptSection("TOOLS", tools_text or ""),
        PromptSection("WORKSPACE", workspace_text or ""),
        PromptSection("MEMORY", memory_text or ""),
    ]
    return build_prompt(sections, instruction or "Produce the best possible final answer.")


def build_team_prompt(task_history: list[str], team_members_text: str | None = None, current_agent_text: str | None = None, transcript: list[dict] | None = None, activity_log: list[dict] | None = None, instruction: str | None = None) -> str:
    history = "\n".join(f"[{i+1}] {task}" for i, task in enumerate(task_history or []))
    transcript_text = "\n".join(f"{e.get('agent', '')}: {e.get('text', '')}" for e in (transcript or []))
    activity_text = "\n".join(f"- {e.get('agent', '')}: {e.get('summary', '')}" for e in (activity_log or []))
    sections = [
        PromptSection("TASK HISTORY", history),
        PromptSection("TEAM MEMBERS", team_members_text or ""),
        PromptSection("CURRENT AGENT", current_agent_text or ""),
        PromptSection("TEAM TRANSCRIPT", transcript_text),
        PromptSection("TEAM ACTIVITY", activity_text),
    ]
    return build_prompt(sections, instruction or "Continue the team task. Respond with DONE only if the team task is complete under the team's completion policy.")


def build_tool_correction_prompt(previous_tool_call: str, validation_errors: list[str], tool_schema: str) -> str:
    err = "\n".join(f"- {e}" for e in validation_errors)
    instruction = (
        "Fix the tool call.\n"
        "Return ONLY a valid JSON object in this format:\n"
        '{"tool": "...", "args": {...}}\n\n'
        "Do not include any explanation.\n"
        "Do not include extra text."
    )
    return build_prompt([
        PromptSection("PREVIOUS TOOL CALL", previous_tool_call),
        PromptSection("VALIDATION ERRORS", err),
        PromptSection("TOOL SCHEMA", tool_schema),
    ], instruction)
