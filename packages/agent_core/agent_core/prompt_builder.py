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
    ) -> str:
        lines = ["TASK:", task]

        if facts:
            lines.extend(["", "FACTS:"])
            lines.extend([f"- {fact}" for fact in facts])

        if tools is not None and hasattr(tools, "list_specs"):
            specs = tools.list_specs()
            lines.extend(["", "TOOLS:"])
            for spec in specs:
                lines.append(f"- name: {spec.get('name', '')}")
                lines.append(f"  description: {spec.get('description', '')}")
                lines.append(f"  risk: {spec.get('risk', '')}")
                lines.append(f"  parameters: {json.dumps(spec.get('parameters', {}), ensure_ascii=False)}")
            lines.extend(["", "TOOL_CALL_INSTRUCTION:",
                "If you need to use a tool, output ONLY a JSON object in the format:",
                "{\"tool\": \"...\", \"args\": {...}}",
                "If no tool is needed, output the final answer directly."])

        if workspace is not None and hasattr(workspace, "root"):
            lines.extend(["", "WORKSPACE:"])
            lines.append(f"Root: {workspace.root}")
            lines.append(f"Read only: {getattr(workspace, 'read_only', None)}")

        if memory is not None and hasattr(memory, "recall"):
            try:
                recalled = memory.recall(task, limit=5)
                if recalled:
                    lines.extend(["", "MEMORY:"])
                    for entry in recalled:
                        text = getattr(entry, "text", "")
                        if text:
                            lines.append(f"- {text}")
            except Exception:
                pass

        lines.extend(["", "INSTRUCTION:"])
        lines.append(instruction or "Produce the best possible final answer.")
        return "\n".join(lines)
