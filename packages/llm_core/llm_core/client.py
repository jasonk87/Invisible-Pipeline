import time
from uuid import uuid4

from llm_core.types import LLMCallRecord, LLMResult


class LLMClient:
    def __init__(self, model: str = "ollama:gemma:e2b", timeout: int | None = None, generate_fn=None, history: list[dict] | None = None, enable_tracing: bool = False):
        self.model = model
        self.timeout = timeout
        self._generate_fn = generate_fn
        self._history = list(history or [])
        self.enable_tracing = enable_tracing
        self._traces: list[LLMCallRecord] = []

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
        started = time.time()
        response = None
        err = None
        try:
            response = self._resolve_generate_fn()(prompt=prompt, model=self.model, timeout=self.timeout)
            return LLMResult(text=response, model=self.model)
        except Exception as exc:
            err = str(exc)
            raise
        finally:
            ended = time.time()
            if self.enable_tracing:
                self._traces.append(LLMCallRecord(str(uuid4()), self.model, prompt, response, started, ended, int((ended-started)*1000), err))

    def chat(self, message: str) -> LLMResult:
        self._history.append({"role": "user", "content": message})
        prompt = "\n\n".join(f"{item['role'].upper()}:\n{item['content']}" for item in self._history)
        result = self.generate(prompt)
        self._history.append({"role": "assistant", "content": result.text})
        return result

    def clear_history(self) -> None: self._history.clear()
    def add_message(self, role: str, content: str) -> None:
        if role not in {"user", "assistant", "system"}: raise ValueError("role must be one of: user, assistant, system")
        self._history.append({"role": role, "content": content})
    def get_history(self) -> list[dict]: return [dict(item) for item in self._history]
    def get_traces(self) -> list[LLMCallRecord]: return list(self._traces)
    def clear_traces(self) -> None: self._traces.clear()


def format_llm_traces(traces) -> str:
    blocks = []
    for entry in traces:
        rec = entry.get("trace") if isinstance(entry, dict) and "trace" in entry else entry
        agent = entry.get("agent") if isinstance(entry, dict) else None
        blocks.append("="*60)
        blocks.append(f"LLM CALL (agent: {agent or 'unknown'})")
        blocks.append(f"Model: {rec.model}")
        blocks.append(f"Duration: {rec.duration_ms} ms\n")
        blocks.append("PROMPT:\n" + rec.prompt)
        blocks.append("\nRESPONSE:\n" + (rec.response or ""))
    return "\n".join(blocks)
