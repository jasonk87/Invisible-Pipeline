import builtins
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import sys

# local workspace package import for tests
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "workspace_core"))

from tool_core import Tool, ToolGroup, ToolRegistry, ToolResult
from tool_core.builtins import (
    append_file_tool,
    apply_patch_tool,
    command_fact_tool,
    find_files_tool,
    read_file_tool,
    read_text_tool,
    tree_summary_tool,
    write_file_tool,
)
from workspace_core import Workspace


class ToolTests(unittest.TestCase):
    def test_valid_call_returns_tool_result(self):
        tool = Tool("x", "desc", {}, lambda **kwargs: ToolResult(ok=True, output="ok"))
        res = tool.call({})
        self.assertTrue(res.ok)

    def test_handler_exception_becomes_tool_result_false(self):
        def boom(**kwargs):
            raise RuntimeError("boom")

        tool = Tool("x", "desc", {}, boom)
        res = tool.call({})
        self.assertFalse(res.ok)

    def test_invalid_name_raises(self):
        with self.assertRaises(ValueError):
            Tool(" ", "desc", {}, lambda **kwargs: ToolResult(ok=True))


class RegistryTests(unittest.TestCase):
    def test_add_get_call_works(self):
        reg = ToolRegistry()
        t = Tool("x", "desc", {}, lambda **kwargs: ToolResult(ok=True, output="ok"))
        reg.add(t)
        self.assertIs(reg.get("x"), t)
        self.assertTrue(reg.call("x", {}).ok)

    def test_duplicate_add_raises(self):
        reg = ToolRegistry()
        t = Tool("x", "desc", {}, lambda **kwargs: ToolResult(ok=True))
        reg.add(t)
        with self.assertRaises(ValueError):
            reg.add(t)

    def test_missing_tool_call_returns_false(self):
        reg = ToolRegistry()
        self.assertFalse(reg.call("missing", {}).ok)

    def test_remove_works(self):
        reg = ToolRegistry()
        reg.add(Tool("x", "desc", {}, lambda **kwargs: ToolResult(ok=True)))
        reg.remove("x")
        self.assertIsNone(reg.get("x"))

    def test_list_specs_includes_fields(self):
        reg = ToolRegistry()
        reg.add(Tool("x", "desc", {"a": 1}, lambda **kwargs: ToolResult(ok=True), risk="safe"))
        spec = reg.list_specs()[0]
        self.assertEqual(set(spec.keys()), {"name", "description", "parameters", "risk"})


class GroupTests(unittest.TestCase):
    def test_routes_known_action(self):
        t = Tool("a", "desc", {}, lambda **kwargs: ToolResult(ok=True, output="ok"))
        g = ToolGroup("group", "desc", {"a": t})
        self.assertTrue(g.call({"action": "a"}).ok)

    def test_unknown_action_fails(self):
        g = ToolGroup("group", "desc", {})
        self.assertFalse(g.call({"action": "x"}).ok)

    def test_missing_action_fails(self):
        g = ToolGroup("group", "desc", {})
        self.assertFalse(g.call({}).ok)

    def test_list_spec_includes_action_options(self):
        t = Tool("a", "desc", {}, lambda **kwargs: ToolResult(ok=True))
        g = ToolGroup("group", "desc", {"a": t})
        spec = g.list_spec()
        self.assertIn("action", spec["parameters"]["properties"])


class BuiltinTests(unittest.TestCase):
    def test_builtins_construct_without_repo_tools_import_at_package_import_time(self):
        self.assertEqual(tree_summary_tool().name, "tree_summary")
        self.assertEqual(read_text_tool().name, "read_text")

    def test_handlers_call_repo_tools_lazily(self):
        real_import = builtins.__import__

        class RepoToolsStub:
            @staticmethod
            def tree_summary(root="."):
                return "TREE"

        def fake_import(name, *args, **kwargs):
            if name == "repo_tools":
                return RepoToolsStub
            return real_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=fake_import):
            res = tree_summary_tool().call({"root": "."})
            self.assertTrue(res.ok)
            self.assertEqual(res.output, "TREE")

    def test_unavailable_repo_tools_returns_error(self):
        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "repo_tools":
                raise ImportError("missing")
            return real_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=fake_import):
            res = read_text_tool().call({"path": "x"})
            self.assertFalse(res.ok)
            self.assertIn("repo_tools is not installed", res.error)


class WorkspaceFileToolTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "a.txt").write_text("old text\n", encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def test_read_file_tool_reads_through_workspace(self):
        ws = Workspace(root=str(self.root), read_only=True)
        res = read_file_tool(ws).call({"path": "a.txt"})
        self.assertTrue(res.ok)
        self.assertIn("old text", res.output)

    def test_read_file_tool_handles_workspace_error(self):
        ws = Workspace(root=str(self.root), read_only=True)
        res = read_file_tool(ws).call({"path": "missing.txt"})
        self.assertFalse(res.ok)

    def test_write_file_tool_writes_and_respects_overwrite(self):
        ws = Workspace(root=str(self.root), read_only=False)
        tool = write_file_tool(ws)
        self.assertTrue(tool.call({"path": "b.txt", "content": "x"}).ok)
        self.assertFalse(tool.call({"path": "b.txt", "content": "y", "overwrite": False}).ok)

    def test_write_file_tool_read_only_fails(self):
        ws = Workspace(root=str(self.root), read_only=True)
        res = write_file_tool(ws).call({"path": "b.txt", "content": "x"})
        self.assertFalse(res.ok)

    def test_append_file_tool_appends_and_read_only_fails(self):
        ws = Workspace(root=str(self.root), read_only=False)
        self.assertTrue(append_file_tool(ws).call({"path": "a.txt", "content": "more"}).ok)
        ws_ro = Workspace(root=str(self.root), read_only=True)
        self.assertFalse(append_file_tool(ws_ro).call({"path": "a.txt", "content": "x"}).ok)

    def test_apply_patch_exact_dry_run_no_write(self):
        ws = Workspace(root=str(self.root), read_only=False)
        res = apply_patch_tool(ws).call({"path": "a.txt", "search": "old text", "replace": "new text", "dry_run": True, "match_mode": "exact"})
        self.assertTrue(res.ok)
        self.assertIn("dry run", res.output.lower())
        self.assertIn("old text", (self.root / "a.txt").read_text(encoding="utf-8"))

    def test_apply_patch_exact_write(self):
        ws = Workspace(root=str(self.root), read_only=False)
        res = apply_patch_tool(ws).call({"path": "a.txt", "search": "old text", "replace": "new text", "dry_run": False, "match_mode": "exact"})
        self.assertTrue(res.ok)
        self.assertIn("new text", (self.root / "a.txt").read_text(encoding="utf-8"))

    def test_apply_patch_zero_and_multiple_matches_fail(self):
        ws = Workspace(root=str(self.root), read_only=False)
        t = apply_patch_tool(ws)
        self.assertFalse(t.call({"path": "a.txt", "search": "missing", "replace": "x"}).ok)
        (self.root / "m.txt").write_text("x\nx\n", encoding="utf-8")
        self.assertFalse(t.call({"path": "m.txt", "search": "x", "replace": "y"}).ok)

    def test_apply_patch_invalid_mode_fails(self):
        ws = Workspace(root=str(self.root), read_only=False)
        self.assertFalse(apply_patch_tool(ws).call({"path": "a.txt", "search": "old", "replace": "new", "match_mode": "bad"}).ok)

    def test_apply_patch_line_endings_and_whitespace_modes(self):
        ws = Workspace(root=str(self.root), read_only=False)
        (self.root / "le.txt").write_text("A\r\nB\r\n", encoding="utf-8")
        t = apply_patch_tool(ws)
        self.assertTrue(t.call({"path": "le.txt", "search": "A\nB", "replace": "X\nY", "dry_run": False, "match_mode": "line_endings"}).ok)
        (self.root / "ws.txt").write_text("alpha    beta\n", encoding="utf-8")
        self.assertTrue(t.call({"path": "ws.txt", "search": "alpha beta", "replace": "gamma", "dry_run": False, "match_mode": "whitespace"}).ok)

    def test_apply_patch_read_only_write_fails(self):
        ws = Workspace(root=str(self.root), read_only=True)
        res = apply_patch_tool(ws).call({"path": "a.txt", "search": "old text", "replace": "new", "dry_run": False})
        self.assertFalse(res.ok)


if __name__ == "__main__":
    unittest.main()
