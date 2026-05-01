import os
import unittest
from pathlib import Path

from env_core import ensure_env_loaded, env_path, get_env, require_env
import env_core.loader as loader


class EnvCoreTests(unittest.TestCase):
    def setUp(self):
        self.path = env_path()
        self.original_exists = self.path.exists()
        self.original_content = self.path.read_text(encoding="utf-8") if self.original_exists else None
        self.saved = dict(os.environ)
        loader._LOADED = False

    def tearDown(self):
        loader._LOADED = False
        os.environ.clear()
        os.environ.update(self.saved)
        if self.original_exists:
            self.path.write_text(self.original_content, encoding="utf-8")
        elif self.path.exists():
            self.path.unlink()

    def _write_env(self, text: str):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(text, encoding="utf-8")

    def test_env_path_points_to_env_dotenv(self):
        self.assertTrue(str(self.path).endswith("packages/env_core/env/.env"))

    def test_missing_env_does_not_crash(self):
        if self.path.exists():
            self.path.unlink()
        ensure_env_loaded()
        self.assertTrue(loader._LOADED)

    def test_key_value_loads(self):
        self._write_env("A=1\n")
        self.assertEqual(get_env("A"), "1")

    def test_comments_and_blank_ignored(self):
        self._write_env("\n# comment\nB=2\n")
        self.assertEqual(get_env("B"), "2")

    def test_quoted_values_handled(self):
        self._write_env("Q1='hello'\nQ2=\"world\"\n")
        self.assertEqual(get_env("Q1"), "hello")
        self.assertEqual(get_env("Q2"), "world")

    def test_existing_env_not_overwritten(self):
        os.environ["A"] = "keep"
        self._write_env("A=replace\n")
        self.assertEqual(get_env("A"), "keep")

    def test_get_env_loads_lazily(self):
        self._write_env("X=9\n")
        self.assertFalse(loader._LOADED)
        self.assertEqual(get_env("X"), "9")
        self.assertTrue(loader._LOADED)

    def test_require_env_returns_value(self):
        self._write_env("Y=ok\n")
        self.assertEqual(require_env("Y"), "ok")

    def test_require_env_raises_when_missing(self):
        self._write_env("Z=\n")
        with self.assertRaises(RuntimeError):
            require_env("MISSING")

    def test_ensure_env_loaded_only_once(self):
        self._write_env("ONE=1\n")
        ensure_env_loaded()
        self.path.write_text("ONE=2\n", encoding="utf-8")
        ensure_env_loaded()
        self.assertEqual(get_env("ONE"), "1")


if __name__ == "__main__":
    unittest.main()
