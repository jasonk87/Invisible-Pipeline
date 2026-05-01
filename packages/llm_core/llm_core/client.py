from llm_core.types import LLMResult


class LLMClient:
    def __init__(
        self,
        model: str = "ollama:gemma:e2b",
        timeout: int | None = None,
        generate_fn=None,
        history: list[dict] | None = None,
    ):
        self.model = model
        self.timeout = timeout
        self._generate_fn = generate_fn
        self._history = list(history or [])

    def _resolve_generate_fn(self):
        if self._generate_fn is not None:
            return self._generate_fn
        try:
            from model_router import generate
        except ImportError as exc:
            raise RuntimeError("model_router.generate is unavailable") from exc
        self._generate_fn = generate
        return self._generate_fn

    def generate(self, prompt: str) -> LLMResult:
        generate_fn = self._resolve_generate_fn()
        response = generate_fn(prompt=prompt, model=self.model, timeout=self.timeout)
        return LLMResult(text=response, model=self.model)

    def chat(self, message: str) -> LLMResult:
        self._history.append({"role": "user", "content": message})
        prompt = "\n\n".join(f"{item['role'].upper()}:\n{item['content']}" for item in self._history)
        result = self.generate(prompt)
        self._history.append({"role": "assistant", "content": result.text})
        return result

    def clear_history(self) -> None:
        self._history.clear()

    def add_message(self, role: str, content: str) -> None:
        if role not in {"user", "assistant", "system"}:
            raise ValueError("role must be one of: user, assistant, system")
        self._history.append({"role": role, "content": content})

    def get_history(self) -> list[dict]:
        return [dict(item) for item in self._history]
