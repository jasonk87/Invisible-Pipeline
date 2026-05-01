MODEL_CONTEXT_WINDOWS = {
    "ollama:gemma:e2b": 32768,
    "ollama:gemma4:e2b": 32768,
    "ollama:gemma4": 32768,
    "ollama:llama3.2": 32768,
    "gemini-2.0-flash-001": 1_048_576,
}

OLLAMA_UNKNOWN_FALLBACK = 32768
GEMINI_UNKNOWN_FALLBACK = 1_048_576
GENERIC_UNKNOWN_FALLBACK = 32768


def get_context_window(model: str, provided: int | None) -> int:
    if provided is not None:
        return provided
    if model in MODEL_CONTEXT_WINDOWS:
        return MODEL_CONTEXT_WINDOWS[model]
    if model.startswith("ollama:"):
        return OLLAMA_UNKNOWN_FALLBACK
    if model.startswith("gemini"):
        return GEMINI_UNKNOWN_FALLBACK
    return GENERIC_UNKNOWN_FALLBACK


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)
