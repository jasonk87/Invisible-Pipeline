from invisible_pipeline import run_pipeline
from model_router import generate


result = run_pipeline(
    task="Explain the cleanest architecture for a small AI assistant.",
    model="ollama:gemma:e2b",
    max_rounds=4,
    timeout=600,
    generate_fn=generate,
)

print(result.final_answer)
