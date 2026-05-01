import builtins
import unittest
from unittest.mock import patch

from agent_core import Agent, AgentStep, PromptBuilder


class PBTests(unittest.TestCase):
    def test_task_always_included(self):
        p = PromptBuilder().build("do x")
        self.assertIn("TASK:\ndo x", p)

    def test_facts_only_when_present(self):
        self.assertNotIn("FACTS:", PromptBuilder().build("t"))
        self.assertIn("FACTS:", PromptBuilder().build("t", facts=["f"]))

    def test_tools_section_only_when_tools_exist(self):
        class T:
            def list_specs(self):
                return [{"name": "a", "description": "d", "risk": "safe", "parameters": {"x": 1}}]

        p = PromptBuilder().build("t", tools=T())
        self.assertIn("TOOLS:", p)
        self.assertIn("name: a", p)

    def test_workspace_section_only_when_workspace_exists(self):
        class W:
            root = "/tmp"
            read_only = True

        self.assertNotIn("WORKSPACE:", PromptBuilder().build("t"))
        self.assertIn("WORKSPACE:", PromptBuilder().build("t", workspace=W()))

    def test_memory_recall_included_when_available(self):
        class E:
            text = "mem"

        class M:
            def recall(self, task, limit=5):
                return [E()]

        p = PromptBuilder().build("t", memory=M())
        self.assertIn("MEMORY:", p)
        self.assertIn("- mem", p)

    def test_memory_recall_failure_does_not_crash(self):
        class M:
            def recall(self, task, limit=5):
                raise RuntimeError("x")

        p = PromptBuilder().build("t", memory=M())
        self.assertIn("TASK:", p)

    def test_default_instruction_included(self):
        p = PromptBuilder().build("t")
        self.assertIn("Produce the best possible final answer.", p)

    def test_custom_instruction_overrides_default(self):
        p = PromptBuilder().build("t", instruction="Do Y")
        self.assertIn("Do Y", p)


class AgentCoreTests(unittest.TestCase):
    def test_build_prompt_passes_components(self):
        captured = {}

        class PB:
            def build(self, **kwargs):
                captured.update(kwargs)
                return "X"

        a = Agent(response_mode="raw", generate_fn=lambda **kwargs: "ok", tools=1, workspace=2, memory=3, prompt_builder=PB())
        a.build_prompt("task", ["f"], "i")
        self.assertEqual(captured["task"], "task")
        self.assertEqual(captured["facts"], ["f"])
        self.assertEqual(captured["tools"], 1)

    def test_raw_mode_uses_prompt_builder_output(self):
        class PB:
            def build(self, **kwargs):
                return "PROMPT"

        calls = []

        def gen(**kwargs):
            calls.append(kwargs)
            return "ok"

        a = Agent(response_mode="raw", generate_fn=gen, prompt_builder=PB())
        a.generate("task")
        self.assertEqual(calls[0]["prompt"], "PROMPT")

    def test_think_mode_uses_prompt_builder_for_first_call(self):
        class PB:
            def build(self, **kwargs):
                return "THINK_PROMPT"

        calls = []

        def gen(**kwargs):
            calls.append(kwargs)
            return "notes" if len(calls) == 1 else "final"

        a = Agent(response_mode="think", generate_fn=gen, prompt_builder=PB())
        res = a.generate("task")
        self.assertEqual(calls[0]["prompt"], "THINK_PROMPT")
        self.assertEqual(res.text, "final")

    def test_invalid_response_mode_raises(self):
        with self.assertRaises(ValueError):
            Agent(response_mode="bad")

    def test_pipeline_mode_passes_expected_args(self):
        captured = {}

        class P:
            final_answer = "ans"
            completed = True
            rounds_used = 2

        def pipe(**kwargs):
            captured.update(kwargs)
            return P()

        gen = lambda **kwargs: "x"
        a = Agent(response_mode="pipeline", pipeline_fn=pipe, generate_fn=gen, model="m", max_rounds=9, timeout=4)
        a.generate("task", facts=["f"])
        self.assertEqual(captured["task"], "task")
        self.assertIs(captured["generate_fn"], gen)

    def test_next_step_returns_final_agent_step(self):
        a = Agent(response_mode="raw", generate_fn=lambda **kwargs: "ok")
        step = a.next_step("task")
        self.assertIsInstance(step, AgentStep)

    def test_default_generate_fn_is_lazy(self):
        real_import = builtins.__import__
        calls = []

        class RouterStub:
            @staticmethod
            def generate(**kwargs):
                calls.append(kwargs)
                return "ok"

        def fake_import(name, *args, **kwargs):
            if name == "model_router":
                return RouterStub
            return real_import(name, *args, **kwargs)

        a = Agent(response_mode="raw", generate_fn=None)
        with patch("builtins.__import__", side_effect=fake_import):
            out = a.generate("task")
        self.assertEqual(out.text, "ok")
        self.assertTrue(calls)


if __name__ == "__main__":
    unittest.main()
