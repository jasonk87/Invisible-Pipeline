import unittest

from prompt_core import PromptSection, build_agent_prompt, build_prompt, build_team_prompt, build_tool_correction_prompt


class PromptCoreTests(unittest.TestCase):
    def test_build_prompt_order_and_instruction(self):
        p = build_prompt([PromptSection("A", "x"), PromptSection("B", "y")], instruction="do")
        self.assertTrue(p.index("A:") < p.index("B:"))
        self.assertIn("INSTRUCTION:\ndo", p)

    def test_empty_sections_omitted(self):
        p = build_prompt([PromptSection("A", ""), PromptSection("B", "y")])
        self.assertNotIn("A:", p)
        self.assertIn("B:\ny", p)

    def test_agent_identity_and_facts_rendering(self):
        p = build_agent_prompt("task", agent_name="n", agent_role="r", agent_persona="p", facts=["f1"])
        self.assertIn("AGENT:", p)
        self.assertIn("Name: n", p)
        self.assertIn("- f1", p)
        self.assertIn("Do not invent tool results", p)
        self.assertIn("best grounded answer possible", p)

    def test_team_history_transcript_activity_rendering(self):
        p = build_team_prompt(["t1", "t2"], transcript=[{"agent": "a", "text": "x"}], activity_log=[{"agent": "a", "summary": "did y"}])
        self.assertIn("[1] t1", p)
        self.assertIn("a: x", p)
        self.assertIn("- a: did y", p)
        self.assertIn("Follow your CURRENT AGENT role", p)
        self.assertIn("Do not repeat prior work", p)
        self.assertIn("Respond with DONE only if", p)

    def test_tool_correction_prompt_contains_strict_instruction(self):
        p = build_tool_correction_prompt("bad", ["err"], "schema")
        self.assertIn("PREVIOUS TOOL CALL:", p)
        self.assertIn('{"tool": "...", "args": {...}}', p)
        self.assertIn("Do not include extra text.", p)
        self.assertIn("include all required arguments", p)
        self.assertIn("Do not include markdown", p)


if __name__ == "__main__":
    unittest.main()
