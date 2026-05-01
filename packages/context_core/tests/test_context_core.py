import unittest

from context_core import ContextBuilder, ContextSection, ContextPackResult
from context_core.policies import estimate_tokens


class ContextCoreTests(unittest.TestCase):
    def _gen(self, **kwargs):
        return "compact text"

    def test_preserve_sections_cannot_be_modified(self):
        ctx = ContextBuilder("ollama:gemma:e2b", self._gen)
        ctx.add("rules", "KEEP_ME", policy="preserve")
        res = ctx.pack("task")
        self.assertTrue(res.ok)
        self.assertIn("KEEP_ME", res.text)

    def test_preserve_overflow_triggers_error(self):
        ctx = ContextBuilder("ollama:gemma:e2b", self._gen, context_window=20, max_usage_ratio=0.5)
        ctx.add("rules", "x" * 1000, policy="preserve")
        res = ctx.pack("task")
        self.assertFalse(res.ok)
        self.assertTrue(res.errors)

    def test_compact_sections_are_summarized(self):
        called = {"v": False}

        def gen(**kwargs):
            called["v"] = True
            return "summary"

        ctx = ContextBuilder("ollama:gemma:e2b", gen, context_window=60, max_usage_ratio=0.5)
        ctx.add("chat", "x" * 200, policy="compact")
        res = ctx.pack("task")
        self.assertTrue(called["v"])
        self.assertIn("chat", res.compacted_sections)

    def test_truncate_sections_are_trimmed(self):
        ctx = ContextBuilder("ollama:gemma:e2b", self._gen, context_window=80, max_usage_ratio=0.4)
        ctx.add("t", "x" * 200, policy="truncate")
        res = ctx.pack("task")
        self.assertTrue(any("Truncated section" in w for w in res.warnings))

    def test_drop_sections_are_removed(self):
        ctx = ContextBuilder("ollama:gemma:e2b", self._gen, context_window=60, max_usage_ratio=0.3)
        ctx.add("d", "x" * 200, policy="drop")
        res = ctx.pack("task")
        self.assertNotIn("SECTION: d", res.text)
        self.assertIn("d", res.dropped_sections)

    def test_token_estimation_works(self):
        self.assertEqual(estimate_tokens("abcd" * 10), 10)

    def test_pack_returns_structured_result(self):
        ctx = ContextBuilder("ollama:gemma:e2b", self._gen)
        res = ctx.pack("task")
        self.assertIsInstance(res, ContextPackResult)

    def test_compaction_calls_generate_fn(self):
        calls = []

        def gen(**kwargs):
            calls.append(kwargs)
            return "summary"

        ctx = ContextBuilder("ollama:gemma:e2b", gen, context_window=60, max_usage_ratio=0.5)
        ctx.add("chat", "x" * 200, policy="compact")
        ctx.pack("task")
        self.assertTrue(calls)

    def test_failure_returns_ok_false_with_error(self):
        ctx = ContextBuilder("ollama:gemma:e2b", self._gen, context_window=20, max_usage_ratio=0.1)
        ctx.add("pres", "x" * 100, policy="preserve")
        res = ctx.pack("task")
        self.assertFalse(res.ok)
        self.assertTrue(res.errors)

    def test_priority_ordering_respected(self):
        ctx = ContextBuilder("ollama:gemma:e2b", self._gen)
        ctx.add("second", "B", policy="preserve", priority=20)
        ctx.add("first", "A", policy="preserve", priority=10)
        res = ctx.pack("task")
        self.assertLess(res.text.index("SECTION: first"), res.text.index("SECTION: second"))



class PolicyTests(unittest.TestCase):
    def test_explicit_override_wins(self):
        from context_core.policies import get_context_window
        self.assertEqual(get_context_window("ollama:unknown", 12345), 12345)

    def test_known_model_mapping_is_used(self):
        from context_core.policies import get_context_window
        self.assertEqual(get_context_window("ollama:gemma:e2b", None), 32768)

    def test_unknown_ollama_model_uses_ollama_fallback(self):
        from context_core.policies import get_context_window
        self.assertEqual(get_context_window("ollama:my-model", None), 32768)

    def test_unknown_gemini_model_uses_gemini_fallback(self):
        from context_core.policies import get_context_window
        self.assertEqual(get_context_window("gemini-2.5-pro", None), 1048576)

    def test_unknown_generic_model_uses_generic_fallback(self):
        from context_core.policies import get_context_window
        self.assertEqual(get_context_window("custom-model", None), 32768)

if __name__ == "__main__":
    unittest.main()
