import tempfile
import unittest
from pathlib import Path

from memory_core import MemoryEntry, delete_memory, list_memories, recall, remember


class MemoryCoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store_path = str(Path(self.tmp.name) / "memories.jsonl")

    def tearDown(self):
        self.tmp.cleanup()

    def test_remember_stores_and_returns_memory_entry(self):
        entry = remember("Hello", tags=["a"], metadata={"k": "v"}, store_path=self.store_path)
        self.assertIsInstance(entry, MemoryEntry)
        self.assertEqual(entry.text, "Hello")
        self.assertEqual(list_memories(self.store_path)[0].id, entry.id)

    def test_empty_text_raises_value_error(self):
        with self.assertRaises(ValueError):
            remember("   ", store_path=self.store_path)

    def test_list_memories_returns_stored_entries(self):
        remember("one", store_path=self.store_path)
        remember("two", store_path=self.store_path)
        self.assertEqual([m.text for m in list_memories(self.store_path)], ["one", "two"])

    def test_missing_file_returns_empty_list(self):
        self.assertEqual(list_memories(self.store_path), [])

    def test_recall_finds_text_matches(self):
        remember("Jason likes local Ollama models", store_path=self.store_path)
        results = recall("Ollama", store_path=self.store_path)
        self.assertEqual(len(results), 1)

    def test_recall_matches_tags(self):
        remember("x", tags=["user", "models"], store_path=self.store_path)
        results = recall("models", tags=["user"], store_path=self.store_path)
        self.assertEqual(len(results), 1)

    def test_recall_requires_all_requested_tags(self):
        remember("x", tags=["user"], store_path=self.store_path)
        remember("y", tags=["user", "models"], store_path=self.store_path)
        results = recall("", tags=["user", "models"], store_path=self.store_path)
        self.assertEqual([r.text for r in results], ["y"])

    def test_recall_can_search_metadata_values(self):
        remember("x", metadata={"tool": "pytest"}, store_path=self.store_path)
        results = recall("pytest", store_path=self.store_path)
        self.assertEqual(len(results), 1)

    def test_queryless_tagged_recall_returns_newest_matching_entries(self):
        remember("old", tags=["user"], store_path=self.store_path)
        remember("new", tags=["user"], store_path=self.store_path)
        results = recall("", tags=["user"], limit=1, store_path=self.store_path)
        self.assertEqual([r.text for r in results], ["new"])

    def test_delete_memory_removes_entry_and_returns_true(self):
        entry = remember("delete me", store_path=self.store_path)
        deleted = delete_memory(entry.id, store_path=self.store_path)
        self.assertTrue(deleted)
        self.assertEqual(list_memories(self.store_path), [])

    def test_delete_memory_returns_false_for_missing_id(self):
        remember("stay", store_path=self.store_path)
        self.assertFalse(delete_memory("missing", store_path=self.store_path))


if __name__ == "__main__":
    unittest.main()
