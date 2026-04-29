def generation_prompt(task: str) -> str:
    return f"""TASK:
{task}

INSTRUCTION:
Produce the best possible final answer."""


def evaluation_prompt(task: str, answer: str, facts: list[str] | None = None) -> str:
    facts_text = "None" if not facts else "\n".join(facts)
    return f"""TASK:
{task}

FACTS:
{facts_text}

ANSWER:
{answer}

INSTRUCTION:
If the answer fully satisfies the task, output exactly:
[COMPLETE]

Otherwise, output the complete best answer."""
