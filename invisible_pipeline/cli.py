import argparse
import shlex

from invisible_pipeline import command_fact, list_ollama_models, run_pipeline


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m invisible_pipeline")
    parser.add_argument("task", nargs="?")
    parser.add_argument("--model", default="gemini-2.0-flash-001")
    parser.add_argument("--max-rounds", type=int, default=4)
    parser.add_argument("--timeout", type=int, default=None)
    parser.add_argument("--fact-command", action="append", default=[])
    parser.add_argument("--list-ollama-models", action="store_true")

    args = parser.parse_args(argv)

    if args.list_ollama_models:
        for name in list_ollama_models(timeout=args.timeout or 10):
            print(name)
        return 0

    if not args.task:
        parser.error("task is required unless --list-ollama-models is used")

    facts = []
    for fact_command in args.fact_command:
        command = shlex.split(fact_command)
        facts.append(command_fact(command, timeout=args.timeout or 60))

    result = run_pipeline(
        task=args.task,
        max_rounds=args.max_rounds,
        model=args.model,
        facts=facts or None,
        timeout=args.timeout,
    )
    print(result.final_answer)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
