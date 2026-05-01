from dataclasses import dataclass


@dataclass(slots=True)
class PipelineResult:
    final_answer: str
    completed: bool
    rounds_used: int
