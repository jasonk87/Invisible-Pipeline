from memory_core import recall, remember
from invisible_pipeline import run_pipeline
from model_router import generate

remember(
    "Jason prefers local Ollama models and modular reusable AI packages.",
    tags=["user", "preference"],
)

memories = recall("Ollama modular packages", tags=["user"], limit=5)
facts = [f"MEMORY: {m.text}" for m in memories]

result = run_pipeline(
    task="Recommend the next local AI module to build.",
    model="ollama:gemma:e2b",
    max_rounds=4,
    timeout=600,
    facts=facts,
    generate_fn=generate,
)

print(result.final_answer)
