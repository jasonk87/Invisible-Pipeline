import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from memory_core import MemoryEntry, MemoryStore, delete_memory, list_memories, recall, remember


class MemoryCoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_default_store_writes_to_project_local_memories_file(self):
        with patch("memory_core.memory.Path.cwd", return_value=self.base):
            store = MemoryStore()
            store.remember("hello")
            self.assertTrue((self.base / "memories" / "memories.jsonl").exists())

    def test_custom_store_dir_writes_to_that_directory(self):
        store_dir = self.base / "custom"
        store = MemoryStore(store_dir=str(store_dir))
        store.remember("hello")
        self.assertTrue((store_dir / "memories.jsonl").exists())

    def test_custom_filename_works(self):
        store = MemoryStore(store_dir=str(self.base), filename="my_memories.jsonl")
        store.remember("hello")
        self.assertTrue((self.base / "my_memories.jsonl").exists())

    def test_object_methods_remember_recall_list_delete_work(self):
        store = MemoryStore(store_dir=str(self.base))
        entry = store.remember("Jason likes Ollama", tags=["user"])
        self.assertIsInstance(entry, MemoryEntry)
        self.assertEqual(len(store.list_memories()), 1)
        self.assertEqual(len(store.recall("Ollama")), 1)
        self.assertTrue(store.delete_memory(entry.id))
        self.assertEqual(store.list_memories(), [])

    def test_top_level_functions_still_work(self):
        path = str(self.base / "memories.jsonl")
        entry = remember("Hello", store_path=path)
        self.assertIsInstance(entry, MemoryEntry)
        self.assertEqual(len(list_memories(path)), 1)
        self.assertEqual(len(recall("hello", store_path=path)), 1)
        self.assertTrue(delete_memory(entry.id, store_path=path))

    def test_explicit_store_path_still_works(self):
        path = str(self.base / "explicit" / "data.jsonl")
        remember("x", store_path=path)
        self.assertTrue(Path(path).exists())

    def test_empty_text_raises_value_error(self):
        store = MemoryStore(store_dir=str(self.base))
        with self.assertRaises(ValueError):
            store.remember("   ")

    def test_missing_file_returns_empty_list(self):
        store = MemoryStore(store_dir=str(self.base))
        self.assertEqual(store.list_memories(), [])


if __name__ == "__main__":
    unittest.main()
