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


class ReactCorrectionTests(unittest.TestCase):
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
                return type("R", (), {"ok": True, "output": "ok", "error": None})()
        return Tools()

    def test_invalid_tool_call_triggers_correction_prompt_and_executes_corrected_call(self):
        prompts = []
        outputs = ['{"tool":"bad","args":{}}', '{"tool":"write_file","args":{"path":"a","content":"b"}}', 'final']

        def gen(**kwargs):
            prompts.append(kwargs["prompt"])
            return outputs.pop(0)

        tools = self._tools()
        a = Agent(response_mode="raw", execution_style="react", tools=tools, generate_fn=gen, context_builder_factory=OKBuilder, use_context_packing=False)
        res = a.generate("task")
        self.assertTrue(res.completed)
        self.assertEqual(tools.calls, 1)
        self.assertTrue(any("PREVIOUS TOOL CALL:" in p for p in prompts))

    def test_correction_output_must_be_json_tool_call(self):
        outputs = ['{"tool":"bad","args":{}}', 'not json', 'still not json']

        def gen(**kwargs):
            return outputs.pop(0)

        a = Agent(response_mode="raw", execution_style="react", tools=self._tools(), generate_fn=gen, context_builder_factory=OKBuilder, use_context_packing=False)
        res = a.generate("task")
        self.assertEqual(res.stop_reason, "tool_validation_failed")

    def test_retries_stay_within_same_action(self):
        outputs = ['{"tool":"bad","args":{}}', '{"tool":"write_file","args":{"path":"a","content":"b"}}', 'forced']

        def gen(**kwargs):
            return outputs.pop(0)

        tools = self._tools()
        a = Agent(response_mode="raw", execution_style="react", tools=tools, generate_fn=gen, max_actions=1, context_builder_factory=OKBuilder, use_context_packing=False)
        res = a.generate("task")
        self.assertEqual(tools.calls, 1)
        self.assertEqual(res.stop_reason, "max_actions_reached")

    def test_correction_prompt_includes_required_sections(self):
        prompts = []
        outputs = ['{"tool":"bad","args":{}}', '{"tool":"write_file","args":{"path":"a","content":"b"}}', 'final']

        def gen(**kwargs):
            prompts.append(kwargs["prompt"])
            return outputs.pop(0)

        a = Agent(response_mode="raw", execution_style="react", tools=self._tools(), generate_fn=gen, context_builder_factory=OKBuilder, use_context_packing=False)
        a.generate("task")
        corr = next(p for p in prompts if "PREVIOUS TOOL CALL:" in p)
        self.assertIn("VALIDATION ERRORS:", corr)
        self.assertIn("TOOL SCHEMA:", corr)
        self.assertIn('Return ONLY a valid JSON object', corr)

    def test_exhausted_retries_returns_structured_failure(self):
        def gen(**kwargs):
            return '{"tool":"bad","args":{}}'

        a = Agent(response_mode="raw", execution_style="react", tools=self._tools(), generate_fn=gen, context_builder_factory=OKBuilder, use_context_packing=False)
        res = a.generate("task")
        self.assertEqual(res.stop_reason, "tool_validation_failed")
        self.assertIn("last_output", res.metadata)


if __name__ == "__main__":
    unittest.main()
