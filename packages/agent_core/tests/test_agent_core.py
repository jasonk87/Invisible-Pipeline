import unittest

from agent_core import Agent


class OKResult:
    ok = True
    text = "PACKED"
    errors = []


class OKBuilder:
    def __init__(self, **kwargs):
        pass
    def add(self, *args, **kwargs):
        pass
    def pack(self, task):
        return OKResult()


class ReactEventTests(unittest.TestCase):
    def _tools(self):
        class ToolObj:
            name = "write_file"
            parameters = {"path": {"type": "string"}, "content": {"type": "string"}}

        class Tools:
            def __init__(self):
                self.calls = 0
            def get(self, name):
                return ToolObj if name == "write_file" else None
            def list_tools(self):
                return [ToolObj]
            def list_specs(self):
                return [{"name": "write_file", "description": "", "risk": "write", "parameters": ToolObj.parameters}]
            def call(self, name, args):
                self.calls += 1
                return type("R", (), {"ok": True, "output": "ok", "error": None, "metadata": None})()
        return Tools()

    def test_react_metadata_includes_events_and_actions_used(self):
        outputs = ['{"tool":"write_file","args":{"path":"a","content":"b"}}', 'final']
        a = Agent(response_mode="raw", execution_mode="react", tools=self._tools(), generate_fn=lambda **kwargs: outputs.pop(0), context_builder_factory=OKBuilder, use_context_packing=False)
        res = a.generate("task")
        self.assertIn("events", res.metadata)
        self.assertIn("actions_used", res.metadata)

    def test_tool_call_and_observation_and_final_events_recorded(self):
        outputs = ['{"tool":"write_file","args":{"path":"a","content":"b"}}', 'final']
        a = Agent(response_mode="raw", execution_mode="react", tools=self._tools(), generate_fn=lambda **kwargs: outputs.pop(0), context_builder_factory=OKBuilder, use_context_packing=False)
        res = a.generate("task")
        types = [e["type"] for e in res.metadata["events"]]
        self.assertIn("tool_call", types)
        self.assertIn("observation", types)
        self.assertIn("final", types)

    def test_validation_error_event_recorded(self):
        outputs = ['{"tool":"bad","args":{}}', '{"tool":"write_file","args":{"path":"a","content":"b"}}', 'final']
        a = Agent(response_mode="raw", execution_mode="react", tools=self._tools(), generate_fn=lambda **kwargs: outputs.pop(0), context_builder_factory=OKBuilder, use_context_packing=False)
        res = a.generate("task")
        self.assertIn("validation_error", [e["type"] for e in res.metadata["events"]])

    def test_error_event_recorded_on_tool_validation_failed(self):
        a = Agent(response_mode="raw", execution_mode="react", tools=self._tools(), generate_fn=lambda **kwargs: '{"tool":"bad","args":{}}', context_builder_factory=OKBuilder, use_context_packing=False)
        res = a.generate("task")
        self.assertEqual(res.stop_reason, "tool_validation_failed")
        self.assertIn("error", [e["type"] for e in res.metadata["events"]])

    def test_existing_behavior_unchanged_final_completion(self):
        a = Agent(response_mode="raw", execution_mode="react", tools=self._tools(), generate_fn=lambda **kwargs: 'done', context_builder_factory=OKBuilder, use_context_packing=False)
        res = a.generate("task")
        self.assertTrue(res.completed)
        self.assertEqual(res.text, "done")


class FakeLLM:
    def __init__(self, outputs, model="llm:model", timeout=222):
        self.outputs = outputs
        self.model = model
        self.timeout = timeout
        self.prompts = []

    def generate(self, prompt):
        self.prompts.append(prompt)
        return type("R", (), {"text": self.outputs.pop(0)})()


class LLMIntegrationTests(unittest.TestCase):
    def test_agent_accepts_llm_object(self):
        llm = FakeLLM(["ok"])
        a = Agent(llm=llm, response_mode="raw", use_context_packing=False)
        self.assertIs(a.llm, llm)

    def test_raw_mode_uses_llm_generate(self):
        llm = FakeLLM(["raw-output"])
        a = Agent(llm=llm, response_mode="raw", use_context_packing=False)
        r = a.generate("task")
        self.assertEqual(r.text, "raw-output")
        self.assertEqual(len(llm.prompts), 1)

    def test_think_mode_uses_llm_generate_twice(self):
        llm = FakeLLM(["notes", "final"])
        a = Agent(llm=llm, response_mode="think", use_context_packing=False)
        r = a.generate("task")
        self.assertEqual(r.text, "final")
        self.assertEqual(len(llm.prompts), 2)

    def test_react_mode_uses_llm_generate(self):
        llm = FakeLLM(["final-answer"])
        a = Agent(llm=llm, response_mode="raw", execution_mode="react", tools=ReactEventTests()._tools(), use_context_packing=False)
        r = a.generate("task")
        self.assertEqual(r.text, "final-answer")
        self.assertEqual(len(llm.prompts), 1)

    def test_pipeline_mode_uses_adapter_that_calls_llm(self):
        llm = FakeLLM(["pipeline-gen"])
        seen = {}

        def fake_pipeline(**kwargs):
            seen["generate_fn"] = kwargs["generate_fn"]
            generated = kwargs["generate_fn"]("p")
            return type("P", (), {"final_answer": generated, "completed": True, "rounds_used": 1})()

        a = Agent(llm=llm, response_mode="pipeline", pipeline_fn=fake_pipeline, use_context_packing=False)
        r = a.generate("task")
        self.assertEqual(r.text, "pipeline-gen")
        self.assertIsNotNone(seen["generate_fn"])

    def test_existing_generate_fn_behavior_still_works(self):
        calls = []

        def stub_generate(**kwargs):
            calls.append(kwargs)
            return "ok"

        a = Agent(generate_fn=stub_generate, response_mode="raw", use_context_packing=False)
        r = a.generate("task")
        self.assertEqual(r.text, "ok")
        self.assertEqual(calls[0]["model"], "ollama:gemma:e2b")

    def test_llm_core_not_required_when_llm_not_provided(self):
        a = Agent(generate_fn=lambda **kwargs: "ok", response_mode="raw", use_context_packing=False)
        self.assertEqual(a.generate("task").text, "ok")


class AgentIdentityTests(unittest.TestCase):
    def test_default_name_and_role_and_persona(self):
        a = Agent(generate_fn=lambda **kwargs: "ok", use_context_packing=False)
        self.assertEqual(a.name, "agent")
        self.assertEqual(a.role, "General assistant")
        self.assertIsNone(a.persona)

    def test_blank_name_raises(self):
        with self.assertRaises(ValueError):
            Agent(name="   ", generate_fn=lambda **kwargs: "ok")

    def test_blank_role_becomes_default_and_persona_blank_none(self):
        a = Agent(name="x", role="  ", persona="  ", generate_fn=lambda **kwargs: "ok")
        self.assertEqual(a.role, "General assistant")
        self.assertIsNone(a.persona)

    def test_role_persona_whitespace_stripped(self):
        a = Agent(name=" x ", role="  coder ", persona=" concise ", generate_fn=lambda **kwargs: "ok")
        self.assertEqual(a.name, "x")
        self.assertEqual(a.role, "coder")
        self.assertEqual(a.persona, "concise")

    def test_build_prompt_includes_agent_section_and_default_role(self):
        a = Agent(name="builder", generate_fn=lambda **kwargs: "ok", use_context_packing=False)
        prompt = a.build_prompt("task")
        self.assertIn("AGENT:", prompt)
        self.assertIn("Name: builder", prompt)
        self.assertIn("Role: General assistant", prompt)


class PromptBuilderIdentityTests(unittest.TestCase):
    def test_agent_section_with_name_role_persona(self):
        from agent_core.prompt_builder import PromptBuilder

        p = PromptBuilder().build("task", agent_name="builder", agent_role="Writes implementation code.", agent_persona="Practical")
        self.assertIn("AGENT:", p)
        self.assertIn("Name: builder", p)
        self.assertIn("Role: Writes implementation code.", p)
        self.assertIn("Persona: Practical", p)

    def test_persona_omitted_when_none(self):
        from agent_core.prompt_builder import PromptBuilder

        p = PromptBuilder().build("task", agent_name="builder", agent_role="Writes implementation code.", agent_persona=None)
        self.assertNotIn("Persona:", p)


class PromptCoreIntegrationFallbackTests(unittest.TestCase):
    def test_tool_correction_prompt_contains_required_sections(self):
        prompts = []
        outputs = ['{"tool":"bad","args":{}}', '{"tool":"write_file","args":{"path":"a","content":"b"}}', 'final']

        def stub_generate(**kwargs):
            prompts.append(kwargs["prompt"])
            return outputs.pop(0)

        a = Agent(response_mode="raw", execution_mode="react", tools=ReactEventTests()._tools(), generate_fn=stub_generate, context_builder_factory=OKBuilder, use_context_packing=False)
        a.generate("task")
        correction_prompt = prompts[1]
        self.assertIn("PREVIOUS TOOL CALL:", correction_prompt)
        self.assertIn("VALIDATION ERRORS:", correction_prompt)
        self.assertIn("TOOL SCHEMA:", correction_prompt)

    def test_agent_core_fallback_without_prompt_core(self):
        import builtins

        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "prompt_core":
                raise ImportError("missing")
            return real_import(name, *args, **kwargs)

        builtins.__import__ = fake_import
        try:
            a = Agent(name="builder", generate_fn=lambda **kwargs: "ok", use_context_packing=False)
            prompt = a.build_prompt("task")
            self.assertIn("AGENT:", prompt)
            self.assertIn("Role: General assistant", prompt)
        finally:
            builtins.__import__ = real_import


class AgentTraceCollectionTests(unittest.TestCase):
    def test_collect_llm_traces_supported(self):
        class L:
            def get_traces(self):
                return ["t"]
        a = Agent(llm=L(), generate_fn=lambda **kwargs: "ok")
        self.assertEqual(a.collect_llm_traces(), ["t"])

    def test_collect_llm_traces_unsupported(self):
        a = Agent(llm=object(), generate_fn=lambda **kwargs: "ok")
        self.assertEqual(a.collect_llm_traces(), [])


class DebugViewerTests(unittest.TestCase):
    def test_format_handles_empty_metadata(self):
        from agent_core.debug_viewer import format_debug_report
        r = type("R", (), {"metadata": None, "events": None, "completed": False, "stop_reason": "x"})()
        out = format_debug_report(r)
        self.assertIn("SUMMARY", out)

    def test_summary_and_events_and_activity(self):
        from agent_core.debug_viewer import format_debug_report
        r = type("R", (), {"metadata": {"session_id": "s1", "activity_log": [{"agent": "a", "summary": "did"}], "events": [{"type": "decision", "title": "Generated next decision"}]}, "events": [{"type": "tool_call", "title": "Calling tool: read_file"}], "completed": True, "stop_reason": "done"})()
        out = format_debug_report(r)
        self.assertIn("session_id: s1", out)
        self.assertIn("[tool_call] Calling tool: read_file", out)
        self.assertIn("- a: did", out)

    def test_llm_trace_object_and_truncation(self):
        from agent_core.debug_viewer import format_debug_report
        trace = type("T", (), {"model": "m", "duration_ms": 1, "error": None, "prompt": "p"*5000, "response": "r"*5000})()
        r = {"metadata": {"llm_traces": [{"agent": "a", "trace": trace}]}}
        out = format_debug_report(r)
        self.assertIn("LLM CALL 1", out)
        self.assertIn("...[truncated]", out)

    def test_tool_traces_render(self):
        from agent_core.debug_viewer import format_debug_report
        r = {"metadata": {"tool_traces": [{"agent": "a", "tool_name": "web_search", "duration_ms": 10, "args": {"q": "x"}}]}}
        out = format_debug_report(r)
        self.assertIn("TOOL CALL 1", out)
        self.assertIn("Tool: web_search", out)

    def test_cli_loads_json_and_invalid_file(self):
        from agent_core.debug_viewer import _main
        import tempfile, json
        from pathlib import Path
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "debug.json"
            p.write_text(json.dumps({"metadata": {"session_id": "s"}}), encoding="utf-8")
            self.assertEqual(_main([str(p)]), 0)
            self.assertNotEqual(_main([str(Path(d)/"missing.json")]), 0)


if __name__ == "__main__":
    unittest.main()
