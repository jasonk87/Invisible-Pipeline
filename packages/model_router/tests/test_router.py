import json
import unittest
from unittest.mock import patch

from model_router.router import generate, list_models


class RouterTests(unittest.TestCase):
    @patch("model_router.router._generate_ollama")
    def test_default_model_is_ollama_gemma_e2b(self, mock_ollama):
        mock_ollama.return_value = "ok"
        generate("p")
        mock_ollama.assert_called_once_with("p", "gemma:e2b", None)

    @patch("model_router.router._generate_ollama")
    def test_ollama_routing_and_prefix_stripping(self, mock_ollama):
        mock_ollama.return_value = "ok"
        generate("p", model="ollama:llama3.2")
        mock_ollama.assert_called_once_with("p", "llama3.2", None)

    @patch("model_router.router.urllib.request.urlopen")
    def test_ollama_timeout_is_passed_to_urlopen(self, mock_urlopen):
        mock_urlopen.return_value.__enter__.return_value.read.return_value = json.dumps(
            {"response": "ok"}
        ).encode("utf-8")
        from model_router.router import _generate_ollama

        _generate_ollama("prompt", "llama3.2", 777)
        _, kwargs = mock_urlopen.call_args
        self.assertEqual(kwargs["timeout"], 777)

    @patch("model_router.router._generate_gemini")
    def test_gemini_path_used_for_non_ollama_model(self, mock_gemini):
        mock_gemini.return_value = "ok"
        generate("p", model="gemini-2.0-flash-001", timeout=12)
        mock_gemini.assert_called_once_with("p", "gemini-2.0-flash-001", 12)

    @patch("model_router.router.urllib.request.urlopen")
    def test_list_models_parses_and_prefixes_ollama_models(self, mock_urlopen):
        payload = {"models": [{"name": "llama3.2"}, {"name": "mistral"}]}
        mock_urlopen.return_value.__enter__.return_value.read.return_value = json.dumps(payload).encode("utf-8")
        self.assertEqual(
            list_models(),
            ["ollama:llama3.2", "ollama:mistral", "gemini-2.0-flash-001"],
        )

    @patch("model_router.router.urllib.request.urlopen", side_effect=OSError("down"))
    def test_list_models_falls_back_to_gemini_only(self, _mock_urlopen):
        self.assertEqual(list_models(), ["gemini-2.0-flash-001"])


if __name__ == "__main__":
    unittest.main()
