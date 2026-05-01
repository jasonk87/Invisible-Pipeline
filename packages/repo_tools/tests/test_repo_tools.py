import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from repo_tools import command_fact, find_files, read_text, tree_summary


class RepoToolsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "a.py").write_text("print('x')", encoding="utf-8")
        (self.root / "b.md").write_text("hello", encoding="utf-8")
        (self.root / "c.txt").write_text("skip", encoding="utf-8")
        (self.root / "node_modules").mkdir()
        (self.root / "node_modules" / "bad.py").write_text("x", encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def test_find_files_finds_default_code_doc_files(self):
        paths = [f.path for f in find_files(root=str(self.root))]
        self.assertIn("a.py", paths)
        self.assertIn("b.md", paths)

    def test_find_files_ignores_default_ignored_dirs(self):
        paths = [f.path for f in find_files(root=str(self.root))]
        self.assertNotIn("node_modules/bad.py", paths)

    def test_find_files_supports_custom_patterns(self):
        paths = [f.path for f in find_files(root=str(self.root), patterns=["*.txt"])]
        self.assertEqual(paths, ["c.txt"])

    def test_find_files_respects_max_files(self):
        files = find_files(root=str(self.root), max_files=1)
        self.assertEqual(len(files), 1)

    def test_read_text_reads_utf8_text(self):
        self.assertEqual(read_text(str(self.root / "b.md")), "hello")

    def test_read_text_truncates_max_chars(self):
        self.assertEqual(read_text(str(self.root / "b.md"), max_chars=2), "he")

    def test_tree_summary_includes_paths_and_sizes(self):
        summary = tree_summary(root=str(self.root))
        self.assertIn("a.py", summary)
        self.assertIn("bytes", summary)

    @patch("repo_tools.commands.subprocess.run")
    def test_command_fact_uses_list_args_and_shell_false(self, mock_run):
        from subprocess import CompletedProcess

        mock_run.return_value = CompletedProcess(["echo", "ok"], 0, "ok\n", "")
        command_fact(["echo", "ok"])
        args, kwargs = mock_run.call_args
        self.assertEqual(args[0], ["echo", "ok"])
        self.assertIs(kwargs["shell"], False)

    def test_command_fact_captures_stdout(self):
        fact = command_fact(["python", "-c", "print('out')"])
        self.assertIn("STDOUT:\nout", fact)

    def test_command_fact_captures_stderr(self):
        fact = command_fact(["python", "-c", "import sys; print('err', file=sys.stderr)"])
        self.assertIn("STDERR:\nerr", fact)

    def test_command_fact_includes_exit_code(self):
        fact = command_fact(["python", "-c", "import sys; sys.exit(3)"])
        self.assertIn("EXIT_CODE:\n3", fact)

    def test_command_fact_handles_timeout_as_fact_string(self):
        fact = command_fact(["python", "-c", "import time; time.sleep(1)"], timeout=0)
        self.assertIn("EXIT_CODE:\n-1", fact)
        self.assertIn("TIMEOUT after 0s", fact)


if __name__ == "__main__":
    unittest.main()
