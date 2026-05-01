from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from invisible_pipeline import command_fact, run_pipeline


def main() -> None:
    task = "What are three tips for writing clearer technical documentation?"

    try:
        result = run_pipeline(task)
        print("Simple usage result:\n")
        print(result.final_answer)
        print(f"\ncompleted={result.completed}, rounds_used={result.rounds_used}\n")

        python_version_fact = command_fact(["python", "--version"])
        result_with_facts = run_pipeline(
            task="Summarize the local Python version and why it matters for dependency compatibility.",
            facts=[python_version_fact],
        )
        print("Usage with facts result:\n")
        print(result_with_facts.final_answer)
        print(
            f"\ncompleted={result_with_facts.completed}, rounds_used={result_with_facts.rounds_used}"
        )
    except RuntimeError as exc:
        print(f"Runtime error: {exc}")
        print("Set GEMINI_API_KEY before running this example.")


if __name__ == "__main__":
    main()
