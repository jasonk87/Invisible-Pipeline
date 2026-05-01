import json
import os
import urllib.error
import urllib.request

OLLAMA_GENERATE_URL = "http://localhost:11434/api/generate"
OLLAMA_TAGS_URL = "http://localhost:11434/api/tags"
DEFAULT_MODEL = "ollama:gemma:e2b"
DEFAULT_OLLAMA_TIMEOUT = 300
DEFAULT_GEMINI_TIMEOUT = 60
GEMINI_MODELS = ["gemini-2.0-flash-001"]


def generate(prompt: str, model: str | None = None, timeout: int | None = None) -> str:
    selected_model = model or DEFAULT_MODEL
    if selected_model.startswith("ollama:"):
        return _generate_ollama(prompt, selected_model.removeprefix("ollama:"), timeout)
    return _generate_gemini(prompt, selected_model, timeout)


def list_models(timeout: int = 10) -> list[str]:
    models = []
    try:
        with urllib.request.urlopen(OLLAMA_TAGS_URL, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
        names = [m.get("name") for m in payload.get("models", []) if m.get("name")]
        models.extend([f"ollama:{name}" for name in names])
    except (urllib.error.URLError, TimeoutError, OSError):
        pass

    return models + GEMINI_MODELS


def _generate_ollama(prompt: str, model: str, timeout: int | None) -> str:
    body = json.dumps({"model": model, "prompt": prompt, "stream": False}).encode("utf-8")
    request = urllib.request.Request(
        OLLAMA_GENERATE_URL,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    request_timeout = DEFAULT_OLLAMA_TIMEOUT if timeout is None else timeout
    with urllib.request.urlopen(request, timeout=request_timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    text = payload.get("response", "")
    if not text:
        raise RuntimeError("Model returned an empty response")
    return text.strip()


def _generate_gemini(prompt: str, model: str, timeout: int | None) -> str:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set")

    from google import genai

    client = genai.Client(api_key=api_key)
    # timeout is accepted in signature for compatibility; SDK call remains minimal.
    _ = timeout if timeout is not None else DEFAULT_GEMINI_TIMEOUT
    response = client.models.generate_content(model=model, contents=prompt)
    text = response.text
    if not text:
        raise RuntimeError("Model returned an empty response")
    return text.strip()
