import json

from agent_core.modes import ALLOWED_RESPONSE_MODES
from agent_core.prompt_builder import PromptBuilder
from agent_core.types import AgentResult, AgentStep, ToolValidationResult


class Agent:
    MAX_TOOL_FIX_ATTEMPTS = 2

    def __init__(self, name: str = "agent", role: str | None = None, persona: str | None = None, model: str = "ollama:gemma:e2b", response_mode: str = "pipeline", max_rounds: int = 4, timeout: int | None = None, memory=None, tools=None, workspace=None, generate_fn=None, pipeline_fn=None, context_builder_factory=None, prompt_builder=None, use_context_packing: bool = True, context_window: int | None = None, max_context_ratio: float = 0.80, execution_mode: str = "direct", execution_style: str | None = None, max_actions: int = 10, llm=None):
        if response_mode not in ALLOWED_RESPONSE_MODES:
            raise ValueError(f"Invalid response_mode: {response_mode}")
        mode = execution_mode if execution_style is None else execution_style
        if mode not in {"direct", "step", "react"}:
            raise ValueError(f"Invalid execution_mode: {mode}")
        if max_actions < 1:
            raise ValueError("max_actions must be >= 1")
        clean_name=(name or "").strip()
        if not clean_name:
            raise ValueError("name must be non-empty")
        clean_role=(role or "").strip() or "General assistant"
        clean_persona=(persona or "").strip() or None
        self.name=clean_name; self.role=clean_role; self.persona=clean_persona; self.model=model; self.response_mode=response_mode; self.max_rounds=max_rounds; self.timeout=timeout
        self.memory=memory; self.tools=tools; self.workspace=workspace; self.generate_fn=generate_fn; self.pipeline_fn=pipeline_fn
        self.context_builder_factory=context_builder_factory; self.prompt_builder=prompt_builder or PromptBuilder()
        self.use_context_packing=use_context_packing; self.context_window=context_window; self.max_context_ratio=max_context_ratio
        self.execution_mode=mode; self.execution_style=mode; self.max_actions=max_actions; self.llm=llm
        if self.llm is not None and getattr(self.llm, "model", None):
            self.model=getattr(self.llm, "model")
        if timeout is None and self.llm is not None and getattr(self.llm, "timeout", None) is not None:
            self.timeout=getattr(self.llm, "timeout")

    def _get_generate_fn(self):
        if self.generate_fn is not None:
            return self.generate_fn
        from model_router import generate
        return generate

    def _generate_text(self, prompt: str) -> str:
        if self.llm is not None:
            return self.llm.generate(prompt).text
        gen = self._get_generate_fn()
        return gen(prompt=prompt, model=self.model, timeout=self.timeout)

    def build_prompt(self, task: str, facts: list[str] | None = None, instruction: str | None = None) -> str:
        return self.prompt_builder.build(task=task, facts=facts, tools=self.tools, workspace=self.workspace, memory=self.memory, instruction=instruction, agent_name=self.name, agent_role=self.role, agent_persona=self.persona)

    def build_and_pack_prompt(self, task: str, facts: list[str] | None = None, instruction: str | None = None):
        base_prompt=self.build_prompt(task,facts,instruction)
        if not self.use_context_packing:
            return base_prompt, None
        builder_cls=self.context_builder_factory
        if builder_cls is None:
            from context_core import ContextBuilder
            builder_cls=ContextBuilder
        b=builder_cls(model=self.model, generate_fn=self._get_generate_fn(), context_window=self.context_window, max_usage_ratio=self.max_context_ratio)
        b.add("full_prompt", base_prompt, policy="preserve", priority=100)
        r=b.pack(task)
        return (r.text,r) if r.ok else (None,r)

    def _parse_step(self, output: str) -> AgentStep:
        try: payload=json.loads(output)
        except Exception: return AgentStep(kind="final", text=output)
        if isinstance(payload, dict) and "tool" in payload:
            args=payload.get("args", {})
            if args is None: args={}
            if not isinstance(args, dict): return AgentStep(kind="error", text="tool args must be an object")
            return AgentStep(kind="tool_call", tool_name=str(payload["tool"]), tool_args=args)
        return AgentStep(kind="final", text=output)

    def validate_tool_call(self, step: AgentStep) -> ToolValidationResult:
        errors=[]
        if step.kind!="tool_call": return ToolValidationResult(False,["step is not a tool_call"])
        if self.tools is None: return ToolValidationResult(False,["no tools configured"])
        if step.tool_name is None: return ToolValidationResult(False,["missing tool_name"])
        if step.tool_args is not None and not isinstance(step.tool_args, dict): return ToolValidationResult(False,["tool args must be an object"])
        tool=self.tools.get(step.tool_name) if hasattr(self.tools,"get") else None
        if tool is None and hasattr(self.tools,"list_tools"):
            if step.tool_name not in [t.name for t in self.tools.list_tools()]: return ToolValidationResult(False,["unknown tool"])
        elif tool is None and not hasattr(self.tools,"call"):
            return ToolValidationResult(False,["unknown tool"])
        if tool is not None and isinstance(step.tool_args, dict):
            req=tool.parameters.get("required",[]) if isinstance(tool.parameters,dict) else []
            missing=[k for k in req if k not in step.tool_args]
            if missing: return ToolValidationResult(False,[f"missing required args: {', '.join(missing)}"])
        return ToolValidationResult(True,[])

    def _render_tool_schema(self, tool) -> str:
        params=tool.parameters if isinstance(getattr(tool,"parameters",None),dict) else {}
        props=params.get("properties", params) if isinstance(params,dict) else {}
        parts=[f"{k}: {v.get('type','any') if isinstance(v,dict) else 'any'}" for k,v in (props.items() if isinstance(props,dict) else [])]
        return f"{tool.name}({', '.join(parts)})"

    def _run_react(self, task: str, facts: list[str] | None) -> AgentResult:
        actions_used=0; observations=[]; events=[]
        while True:
            merged=list(facts or [])+observations
            packed, pack=self.build_and_pack_prompt(task, merged)
            if packed is None:
                events.append({"type":"error","title":"Agent stopped with error","details":{"stop_reason":"context_error","errors":pack.errors}})
                return AgentResult(text="", completed=False, stop_reason="context_error", metadata={"errors": pack.errors, "events": events, "actions_used": actions_used})
            raw=self._generate_text(packed)
            events.append({"type":"decision","title":"Generated next decision","details":{"raw_output": raw}})
            parsed=self._parse_step(raw)
            if parsed.kind=="final":
                events.append({"type":"final","title":"Final answer produced","details":{"completed": True}})
                return AgentResult(text=parsed.text, completed=True, metadata={"events": events, "actions_used": actions_used})
            if parsed.kind!="tool_call":
                events.append({"type":"error","title":"Agent stopped with error","details":{"stop_reason":"parse_error","errors":[parsed.text]}})
                return AgentResult(text="", completed=False, stop_reason="parse_error", metadata={"errors":[parsed.text], "events": events, "actions_used": actions_used})
            validation=self.validate_tool_call(parsed)
            attempts=0
            while not validation.ok and attempts < self.MAX_TOOL_FIX_ATTEMPTS:
                events.append({"type":"validation_error","title":"Tool call validation failed","details":{"errors": validation.errors}})
                tool=self.tools.get(parsed.tool_name) if (self.tools is not None and hasattr(self.tools,"get") and parsed.tool_name) else None
                schema=self._render_tool_schema(tool) if tool is not None else "unknown_tool(args: ...)"
                try:
                    from prompt_core import build_tool_correction_prompt

                    corr_prompt = build_tool_correction_prompt(raw, validation.errors, schema)
                except ImportError:
                    errors="\n".join(f"- {e}" for e in validation.errors)
                    corr_prompt=(f"PREVIOUS TOOL CALL:\n{raw}\n\n"+f"VALIDATION ERRORS:\n{errors}\n\n"+f"TOOL SCHEMA:\n{schema}\n\n"+"INSTRUCTION:\nFix the tool call.\n"+"Return ONLY a valid JSON object in this format:\n"+'{"tool": "...", "args": {...}}\n\n'+"Do not include any explanation.\n"+"Do not include extra text.")
                raw=self._generate_text(corr_prompt)
                events.append({"type":"decision","title":"Generated next decision","details":{"raw_output": raw}})
                parsed=self._parse_step(raw)
                validation=ToolValidationResult(False,["correction output was not a JSON tool call"]) if parsed.kind!="tool_call" else self.validate_tool_call(parsed)
                attempts += 1
            if not validation.ok:
                events.append({"type":"error","title":"Agent stopped with error","details":{"stop_reason":"tool_validation_failed","errors": validation.errors}})
                return AgentResult(text="", completed=False, stop_reason="tool_validation_failed", metadata={"errors": validation.errors, "last_output": raw, "events": events, "actions_used": actions_used})
            events.append({"type":"tool_call","title":f"Calling tool: {parsed.tool_name}","details":{"tool": parsed.tool_name, "args": parsed.tool_args or {}}})
            r=self.run_tool(parsed); actions_used += 1
            events.append({"type":"observation","title":f"Tool result: {parsed.tool_name}","details":{"ok": getattr(r,'ok',False), "output": getattr(r,'output',''), "error": getattr(r,'error',None), "metadata": getattr(r,'metadata',None)}})
            observations.append(f"OBSERVATION:\n{r.output or r.error}")
            if actions_used >= self.max_actions:
                merged=list(facts or [])+observations
                fp, pack=self.build_and_pack_prompt(task, merged, instruction="You have reached the maximum number of tool actions. Produce the best possible final answer using the information gathered so far.")
                if fp is None:
                    events.append({"type":"error","title":"Agent stopped with error","details":{"stop_reason":"context_error","errors": pack.errors}})
                    return AgentResult(text="", completed=False, stop_reason="context_error", metadata={"errors": pack.errors, "actions_used": actions_used, "events": events})
                final=self._generate_text(fp)
                events.append({"type":"final","title":"Final answer produced","details":{"completed": False}})
                return AgentResult(text=final, completed=False, stop_reason="max_actions_reached", metadata={"actions_used": actions_used, "events": events})

    def _generate_core(self, task: str, facts: list[str] | None = None) -> AgentResult:
        packed, pack=self.build_and_pack_prompt(task,facts)
        if packed is None: return AgentResult(text="", completed=False, stop_reason="context_error", metadata={"errors": pack.errors})
        if self.response_mode=="raw": return AgentResult(text=self._generate_text(packed))
        if self.response_mode=="think":
            notes=self._generate_text(packed+"\n\nINSTRUCTION:\nThink privately and produce useful reasoning notes.")
            final=self._generate_text(packed+"\n\nPRIVATE_NOTES:\n"+notes+"\n\nINSTRUCTION:\nProduce final answer only.")
            return AgentResult(text=final, metadata={"thinking_used": True})
        pipeline=self.pipeline_fn
        if pipeline is None:
            from invisible_pipeline import run_pipeline
            pipeline=run_pipeline
        adapter = lambda prompt, model=None, timeout=None: self._generate_text(prompt)
        pr=pipeline(task=packed, max_rounds=self.max_rounds, model=self.model, facts=None, timeout=self.timeout, generate_fn=adapter)
        return AgentResult(text=pr.final_answer, completed=pr.completed, metadata={"rounds_used": pr.rounds_used})

    def generate(self, task: str, facts: list[str] | None = None) -> AgentResult:
        if self.execution_mode=="react": return self._run_react(task, facts)
        if self.execution_mode=="step":
            s=self.next_step(task, facts)
            return AgentResult(text=s.text, metadata=s.metadata)
        return self._generate_core(task, facts)

    def run_tool(self, step: AgentStep):
        try:
            from tool_core import ToolResult
        except ImportError:
            class ToolResult:
                def __init__(self, ok: bool, output: str = "", error: str | None = None, metadata: dict | None = None):
                    self.ok=ok; self.output=output; self.error=error; self.metadata=metadata
        if step.kind!="tool_call": return ToolResult(ok=False, error="step is not a tool_call")
        if self.tools is None: return ToolResult(ok=False, error="no tools configured")
        if step.tool_name is None: return ToolResult(ok=False, error="missing tool_name")
        return self.tools.call(step.tool_name, step.tool_args or {})

    def next_step(self, task: str, facts: list[str] | None = None) -> AgentStep:
        r=self._generate_core(task,facts)
        return AgentStep(kind="final", text=r.text, metadata=r.metadata)
