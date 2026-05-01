import builtins
import unittest

from llm_core import LLMClient, LLMResult


class LLMCoreTests(unittest.TestCase):
    def test_default_model(self):
        client = LLMClient(generate_fn=lambda **_: "ok")
        self.assertEqual(client.model, "ollama:gemma:e2b")

    def test_generate_calls_generate_fn_with_prompt_model_timeout(self):
        seen = {}

        def stub_generate(**kwargs):
            seen.update(kwargs)
            return "hello"

        client = LLMClient(model="m", timeout=123, generate_fn=stub_generate)
        result = client.generate("prompt")
        self.assertEqual(seen, {"prompt": "prompt", "model": "m", "timeout": 123})
        self.assertIsInstance(result, LLMResult)
        self.assertEqual(result.text, "hello")

    def test_model_router_import_is_lazy(self):
        client = LLMClient(generate_fn=lambda **_: "ok")
        self.assertIsNotNone(client)

    def test_chat_appends_user_and_assistant_messages(self):
        client = LLMClient(generate_fn=lambda **_: "assistant reply")
        result = client.chat("hi")
        self.assertEqual(result.text, "assistant reply")
        self.assertEqual(client.get_history(), [
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "assistant reply"},
        ])

    def test_chat_builds_prompt_from_history(self):
        calls = []

        def stub_generate(**kwargs):
            calls.append(kwargs)
            return "ok"

        client = LLMClient(generate_fn=stub_generate, history=[{"role": "system", "content": "be concise"}])
        client.chat("hello")
        prompt = calls[0]["prompt"]
        self.assertIn("SYSTEM:\nbe concise", prompt)
        self.assertIn("USER:\nhello", prompt)

    def test_clear_history(self):
        client = LLMClient(generate_fn=lambda **_: "ok", history=[{"role": "user", "content": "x"}])
        client.clear_history()
        self.assertEqual(client.get_history(), [])

    def test_add_message_validates_roles(self):
        client = LLMClient(generate_fn=lambda **_: "ok")
        client.add_message("system", "rules")
        with self.assertRaises(ValueError):
            client.add_message("tool", "bad")

    def test_get_history_returns_copy(self):
        client = LLMClient(generate_fn=lambda **_: "ok", history=[{"role": "user", "content": "x"}])
        history = client.get_history()
        history[0]["content"] = "changed"
        self.assertEqual(client.get_history()[0]["content"], "x")

    def test_missing_model_router_raises_at_call_time(self):
        client = LLMClient(generate_fn=None)
        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "model_router":
                raise ImportError("missing")
            return real_import(name, *args, **kwargs)

        builtins.__import__ = fake_import
        try:
            with self.assertRaises(RuntimeError):
                client.generate("hello")
        finally:
            builtins.__import__ = real_import


class LLMTracingTests(unittest.TestCase):
    def test_tracing_disabled_no_traces(self):
        c = LLMClient(generate_fn=lambda **_: "ok", enable_tracing=False)
        c.generate("p")
        self.assertEqual(c.get_traces(), [])

    def test_tracing_enabled_records_trace(self):
        c = LLMClient(generate_fn=lambda **_: "ok", enable_tracing=True)
        c.generate("p")
        traces = c.get_traces()
        self.assertEqual(len(traces), 1)
        self.assertEqual(traces[0].prompt, "p")

    def test_error_still_produces_trace(self):
        c = LLMClient(generate_fn=lambda **_: (_ for _ in ()).throw(RuntimeError("boom")), enable_tracing=True)
        with self.assertRaises(RuntimeError):
            c.generate("p")
        self.assertEqual(len(c.get_traces()), 1)
        self.assertIsNotNone(c.get_traces()[0].error)

    def test_duration_recorded(self):
        c = LLMClient(generate_fn=lambda **_: "ok", enable_tracing=True)
        c.generate("p")
        self.assertIsInstance(c.get_traces()[0].duration_ms, int)


if __name__ == "__main__":
    unittest.main()
