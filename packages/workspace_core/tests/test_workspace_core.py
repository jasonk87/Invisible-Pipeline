import tempfile
import unittest
from pathlib import Path

from workspace_core import Workspace, WorkspaceError


class WorkspaceCoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "src").mkdir()
        (self.root / "src" / "main.py").write_text("print('hello')", encoding="utf-8")
        (self.root / ".git").mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def test_resolve_prevents_escape(self):
        ws = Workspace(root=str(self.root))
        with self.assertRaises(WorkspaceError):
            ws.resolve("../outside.txt")

    def test_resolve_blocks_default_blocked_names(self):
        ws = Workspace(root=str(self.root))
        with self.assertRaises(WorkspaceError):
            ws.resolve(".git/config")

    def test_validate_returns_false_without_raising(self):
        ws = Workspace(root=str(self.root))
        result = ws.validate("../outside")
        self.assertFalse(result.ok)

    def test_exists_is_file_is_dir(self):
        ws = Workspace(root=str(self.root))
        self.assertTrue(ws.exists("src/main.py"))
        self.assertTrue(ws.is_file("src/main.py"))
        self.assertTrue(ws.is_dir("src"))

    def test_read_text_reads_and_truncates(self):
        ws = Workspace(root=str(self.root))
        self.assertEqual(ws.read_text("src/main.py", max_chars=5), "print")

    def test_write_text_fails_in_read_only_mode(self):
        ws = Workspace(root=str(self.root), read_only=True)
        with self.assertRaises(WorkspaceError):
            ws.write_text("x.txt", "hello")

    def test_write_text_creates_directories_when_allowed(self):
        ws = Workspace(root=str(self.root), read_only=False)
        ws.write_text("nested/a.txt", "hello")
        self.assertTrue((self.root / "nested" / "a.txt").exists())

    def test_write_text_respects_overwrite_flag(self):
        ws = Workspace(root=str(self.root), read_only=False)
        ws.write_text("a.txt", "1")
        with self.assertRaises(WorkspaceError):
            ws.write_text("a.txt", "2", overwrite=False)

    def test_append_text_works_when_not_read_only(self):
        ws = Workspace(root=str(self.root), read_only=False)
        ws.write_text("a.txt", "1")
        ws.append_text("a.txt", "2")
        self.assertEqual((self.root / "a.txt").read_text(encoding="utf-8"), "12")

    def test_list_dir_returns_sorted_names(self):
        ws = Workspace(root=str(self.root), read_only=False)
        ws.write_text("b.txt", "b")
        ws.write_text("a.txt", "a")
        names = ws.list_dir(".")
        self.assertEqual(names, sorted(names))

    def test_blocked_paths_custom_list_works(self):
        ws = Workspace(root=str(self.root), blocked_paths=["src/private"])
        (self.root / "src" / "private").mkdir()
        with self.assertRaises(WorkspaceError):
            ws.resolve("src/private/file.txt")

    def test_safe_join_resolves_correctly(self):
        ws = Workspace(root=str(self.root))
        resolved = ws.safe_join("src", "main.py")
        self.assertEqual(Path(resolved), (self.root / "src" / "main.py").resolve())


if __name__ == "__main__":
    unittest.main()
