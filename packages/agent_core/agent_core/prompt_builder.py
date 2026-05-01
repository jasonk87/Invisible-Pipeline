import json


class PromptBuilder:
    def build(
        self,
        task: str,
        facts: list[str] | None = None,
        tools=None,
        workspace=None,
        memory=None,
        instruction: str | None = None,
        agent_name: str | None = None,
        agent_role: str | None = None,
        agent_persona: str | None = None,
    ) -> str:
        tools_text = None
        if tools is not None and hasattr(tools, "list_specs"):
            specs = tools.list_specs()
            lines = []
            for spec in specs:
                lines.append(f"- name: {spec.get('name', '')}")
                lines.append(f"  description: {spec.get('description', '')}")
                lines.append(f"  risk: {spec.get('risk', '')}")
                lines.append(f"  parameters: {json.dumps(spec.get('parameters', {}), ensure_ascii=False)}")
            lines.extend(["", "TOOL_CALL_INSTRUCTION:", "If you need to use a tool, output ONLY a JSON object in the format:", '{"tool": "...", "args": {...}}', "If no tool is needed, output the final answer directly."])
            tools_text = "\n".join(lines)

        workspace_text = None
        if workspace is not None and hasattr(workspace, "root"):
            workspace_text = f"Root: {workspace.root}\nRead only: {getattr(workspace, 'read_only', None)}"

        memory_text = None
        if memory is not None and hasattr(memory, "recall"):
            try:
                recalled = memory.recall(task, limit=5)
                if recalled:
                    memory_text = "\n".join(f"- {getattr(entry, 'text', '')}" for entry in recalled if getattr(entry, "text", ""))
            except Exception:
                pass

        try:
            from prompt_core import build_agent_prompt

            return build_agent_prompt(
                task=task,
                agent_name=agent_name,
                agent_role=agent_role,
                agent_persona=agent_persona,
                facts=facts,
                tools_text=tools_text,
                workspace_text=workspace_text,
                memory_text=memory_text,
                instruction=instruction,
            )
        except ImportError:
            lines = ["TASK:", task]
            if agent_name or agent_role or agent_persona:
                lines.extend(["", "AGENT:"])
                if agent_name:
                    lines.append(f"Name: {agent_name}")
                if agent_role:
                    lines.append(f"Role: {agent_role}")
                if agent_persona:
                    lines.append(f"Persona: {agent_persona}")
            if facts:
                lines.extend(["", "FACTS:"])
                lines.extend([f"- {fact}" for fact in facts])
            if tools_text:
                lines.extend(["", "TOOLS:", tools_text])
            if workspace_text:
                lines.extend(["", "WORKSPACE:", workspace_text])
            if memory_text:
                lines.extend(["", "MEMORY:", memory_text])
            lines.extend(["", "INSTRUCTION:", instruction or "Produce the best possible final answer."])
            return "\n".join(lines)
