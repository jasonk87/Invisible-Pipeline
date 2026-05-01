import io
import json
import subprocess
import unittest
from unittest.mock import patch

from invisible_pipeline import PipelineResult, run_pipeline
from invisible_pipeline.facts import command_fact
from invisible_pipeline.models import generate_text, list_ollama_models
from invisible_pipeline.prompts import evaluation_prompt, generation_prompt


class PromptTests(unittest.TestCase):
    def test_generation_prompt_has_task_and_instruction_only(self):
        prompt = generation_prompt("Solve X")
        self.assertEqual(
            prompt,
            """TASK:
Solve X

INSTRUCTION:
Produce the best possible final answer.""",
        )
        self.assertNotIn("FACTS:", prompt)
        self.assertNotIn("ANSWER:", prompt)

    def test_evaluation_prompt_has_required_sections(self):
        prompt = evaluation_prompt("Solve X", "Answer Y", ["fact 1"])
        self.assertIn("TASK:\nSolve X", prompt)
        self.assertIn("FACTS:\nfact 1", prompt)
        self.assertIn("ANSWER:\nAnswer Y", prompt)
        self.assertIn("INSTRUCTION:", prompt)

    def test_evaluation_prompt_renders_none_for_empty_facts(self):
        prompt_none = evaluation_prompt("T", "A", None)
        prompt_empty = evaluation_prompt("T", "A", [])
        self.assertIn("FACTS:\nNone", prompt_none)
        self.assertIn("FACTS:\nNone", prompt_empty)


class PipelineTests(unittest.TestCase):

    @patch("invisible_pipeline.pipeline.generate_text")
    def test_pipeline_default_model_is_ollama_gemma_e2b(self, mock_generate_text):
        mock_generate_text.side_effect = ["initial answer", "[COMPLETE]"]
        run_pipeline("Task")
        self.assertEqual(mock_generate_text.call_args_list[0].kwargs["model"], "ollama:gemma:e2b")

    @patch("invisible_pipeline.pipeline.generate_text")
    def test_complete_stops_loop_early(self, mock_generate_text):
        mock_generate_text.side_effect = ["initial answer", "[COMPLETE]"]
        result = run_pipeline("Task", max_rounds=4)
        self.assertEqual(result, PipelineResult("initial answer", True, 2))
        self.assertEqual(mock_generate_text.call_count, 2)

    @patch("invisible_pipeline.pipeline.generate_text")
    def test_non_complete_replaces_answer(self, mock_generate_text):
        mock_generate_text.side_effect = ["initial answer", "replacement answer", "[COMPLETE]"]
        result = run_pipeline("Task", max_rounds=4)
        self.assertEqual(result, PipelineResult("replacement answer", True, 3))

    @patch("invisible_pipeline.pipeline.generate_text")
    def test_pipeline_passes_timeout_to_all_calls(self, mock_generate_text):
        mock_generate_text.side_effect = ["initial answer", "[COMPLETE]"]
        run_pipeline("Task", max_rounds=4, timeout=123)
        for call in mock_generate_text.call_args_list:
            self.assertEqual(call.kwargs["timeout"], 123)



    def test_pipeline_uses_injected_generate_fn(self):
        calls = []

        def fake_generate(*, prompt: str, model: str, timeout: int | None = None) -> str:
            calls.append((prompt, model, timeout))
            return "seed" if len(calls) == 1 else "[COMPLETE]"

        result = run_pipeline("Task", generate_fn=fake_generate, timeout=77)
        self.assertEqual(result, PipelineResult("seed", True, 2))
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0][1], "ollama:gemma:e2b")
        self.assertEqual(calls[0][2], 77)


class CommandFactTests(unittest.TestCase):
    @patch("invisible_pipeline.facts.subprocess.run")
    def test_command_uses_list_args_not_shell_string(self, mock_run):
        mock_run.return_value = subprocess.CompletedProcess(["echo", "ok"], 0, "ok\n", "")
        command_fact(["echo", "ok"])
        args, kwargs = mock_run.call_args
        self.assertEqual(args[0], ["echo", "ok"])
        self.assertIs(kwargs["shell"], False)

    def test_stdout_stderr_and_exit_code_included(self):
        fact = command_fact(
            ["python", "-c", "import sys; print('out'); print('err', file=sys.stderr); sys.exit(3)"]
        )
        self.assertIn("EXIT_CODE:\n3", fact)
        self.assertIn("STDOUT:\nout", fact)
        self.assertIn("STDERR:\nerr", fact)

    def test_timeout_returns_fact_string(self):
        fact = command_fact(["python", "-c", "import time; time.sleep(1)"], timeout=0)
        self.assertIn("COMMAND:\npython -c import time; time.sleep(1)", fact)
        self.assertIn("EXIT_CODE:\n-1", fact)
        self.assertIn("STDERR:\nTIMEOUT after 0s", fact)


class ModelTests(unittest.TestCase):
    @patch("invisible_pipeline.models._generate_ollama")
    def test_ollama_prefix_routes_to_ollama(self, mock_ollama):
        mock_ollama.return_value = "x"
        generate_text("p", "ollama:llama3.2", timeout=9)
        mock_ollama.assert_called_once_with("p", "llama3.2", 9)

    @patch("invisible_pipeline.models._generate_gemini")
    def test_non_ollama_routes_to_gemini(self, mock_gemini):
        mock_gemini.return_value = "x"
        generate_text("p", "gemini-2.0-flash-001", timeout=11)
        mock_gemini.assert_called_once_with("p", "gemini-2.0-flash-001", 11)

    @patch("invisible_pipeline.models.urllib.request.urlopen")
    def test_list_ollama_models_parses_names(self, mock_urlopen):
        payload = {"models": [{"name": "llama3.2"}, {"name": "mistral"}, {"other": "x"}]}
        mock_urlopen.return_value.__enter__.return_value.read.return_value = json.dumps(payload).encode("utf-8")
        self.assertEqual(list_ollama_models(), ["llama3.2", "mistral"])

    @patch("invisible_pipeline.models.urllib.request.urlopen")
    def test_ollama_timeout_is_passed_to_urlopen(self, mock_urlopen):
        mock_urlopen.return_value.__enter__.return_value.read.return_value = json.dumps(
            {"response": "ok"}
        ).encode("utf-8")
        from invisible_pipeline.models import _generate_ollama

        _generate_ollama("prompt", "llama3.2", 777)
        _, kwargs = mock_urlopen.call_args
        self.assertEqual(kwargs["timeout"], 777)


if __name__ == "__main__":
    unittest.main()

from io import StringIO
from contextlib import redirect_stdout

from invisible_pipeline.cli import main as cli_main


class CliTests(unittest.TestCase):

    @patch("invisible_pipeline.cli.run_pipeline")
    def test_cli_default_model_is_ollama_gemma_e2b(self, mock_run_pipeline):
        mock_run_pipeline.return_value = PipelineResult("final", True, 2)
        cli_main(["task text"])
        self.assertEqual(mock_run_pipeline.call_args.kwargs["model"], "ollama:gemma:e2b")

    @patch("invisible_pipeline.cli.run_pipeline")
    def test_cli_invokes_run_pipeline_with_options(self, mock_run_pipeline):
        mock_run_pipeline.return_value = PipelineResult("final", True, 2)

        cli_main(["task text", "--model", "m", "--max-rounds", "5", "--timeout", "9"])

        mock_run_pipeline.assert_called_once_with(
            task="task text", max_rounds=5, model="m", facts=None, timeout=9
        )

    @patch("invisible_pipeline.cli.command_fact")
    @patch("invisible_pipeline.cli.run_pipeline")
    def test_repeated_fact_commands_are_collected(self, mock_run_pipeline, mock_command_fact):
        mock_run_pipeline.return_value = PipelineResult("final", True, 2)
        mock_command_fact.side_effect = ["fact1", "fact2"]

        cli_main([
            "task",
            "--fact-command",
            "python --version",
            "--fact-command",
            "pytest -q",
        ])

        self.assertEqual(mock_command_fact.call_count, 2)
        mock_run_pipeline.assert_called_once()
        self.assertEqual(mock_run_pipeline.call_args.kwargs["facts"], ["fact1", "fact2"])

    @patch("invisible_pipeline.cli.command_fact")
    @patch("invisible_pipeline.cli.run_pipeline")
    def test_fact_commands_use_shlex_list_args(self, mock_run_pipeline, mock_command_fact):
        mock_run_pipeline.return_value = PipelineResult("final", True, 2)

        cli_main(["task", "--fact-command", "python --version"])

        args, kwargs = mock_command_fact.call_args
        self.assertEqual(args[0], ["python", "--version"])
        self.assertIn("timeout", kwargs)

    @patch("invisible_pipeline.cli.list_ollama_models")
    @patch("invisible_pipeline.cli.run_pipeline")
    def test_list_ollama_models_prints_and_exits(self, mock_run_pipeline, mock_list):
        mock_list.return_value = ["llama3.2", "mistral"]
        out = StringIO()
        with redirect_stdout(out):
            rc = cli_main(["--list-ollama-models"])
        self.assertEqual(rc, 0)
        self.assertEqual(out.getvalue(), "llama3.2\nmistral\n")
        mock_run_pipeline.assert_not_called()

    @patch("invisible_pipeline.cli.run_pipeline")
    def test_normal_run_prints_final_answer(self, mock_run_pipeline):
        mock_run_pipeline.return_value = PipelineResult("only final", True, 2)
        out = StringIO()
        with redirect_stdout(out):
            cli_main(["task"])
        self.assertEqual(out.getvalue(), "only final\n")
