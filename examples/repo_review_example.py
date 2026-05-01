from repo_tools import tree_summary, command_fact
from model_router import generate
from invisible_pipeline import run_pipeline

facts = [
    "PROJECT TREE:\n" + tree_summary("."),
    "TEST OUTPUT:\n" + command_fact(["pytest", "-q"]),
]

result = run_pipeline(
    task="Review this project and suggest the highest-value next cleanup.",
    facts=facts,
    model="ollama:gemma:e2b",
    timeout=600,
    max_rounds=4,
    generate_fn=generate,
)

print(result.final_answer)
