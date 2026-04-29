from invisible_pipeline.models import generate_text
from invisible_pipeline.prompts import evaluation_prompt, generation_prompt
from invisible_pipeline.types import PipelineResult


COMPLETE_TOKEN = "[COMPLETE]"


def run_pipeline(
    task: str,
    max_rounds: int = 4,
    model: str = "gemini-2.0-flash-001",
    facts: list[str] | None = None,
    timeout: int | None = None,
) -> PipelineResult:
    if not task.strip():
        raise ValueError("task must be a non-empty string")
    if max_rounds < 1:
        raise ValueError("max_rounds must be at least 1")

    answer = generate_text(generation_prompt(task), model, timeout=timeout)
    rounds_used = 1

    for _ in range(max_rounds - 1):
        result = generate_text(evaluation_prompt(task, answer, facts), model, timeout=timeout)
        rounds_used += 1

        if result.strip() == COMPLETE_TOKEN:
            return PipelineResult(
                final_answer=answer,
                completed=True,
                rounds_used=rounds_used,
            )

        answer = result

    return PipelineResult(final_answer=answer, completed=False, rounds_used=rounds_used)
