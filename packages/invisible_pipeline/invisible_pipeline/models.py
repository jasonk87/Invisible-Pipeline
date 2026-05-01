import json
import os
import urllib.error
import urllib.request


OLLAMA_GENERATE_URL = "http://localhost:11434/api/generate"
OLLAMA_TAGS_URL = "http://localhost:11434/api/tags"
OLLAMA_DEFAULT_TIMEOUT = 300


def generate_text(prompt: str, model: str, timeout: int | None = None) -> str:
    if model.startswith("ollama:"):
        return _generate_ollama(prompt, model.removeprefix("ollama:"), timeout)
    return _generate_gemini(prompt, model, timeout)


def list_ollama_models(timeout: int = 10) -> list[str]:
    try:
        with urllib.request.urlopen(OLLAMA_TAGS_URL, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise RuntimeError("Could not reach Ollama at http://localhost:11434") from exc

    models = payload.get("models", [])
    return [m.get("name", "") for m in models if m.get("name")]


def _generate_ollama(prompt: str, model: str, timeout: int | None) -> str:
    request_body = json.dumps({"model": model, "prompt": prompt, "stream": False}).encode("utf-8")
    request = urllib.request.Request(
        OLLAMA_GENERATE_URL,
        data=request_body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    request_timeout = OLLAMA_DEFAULT_TIMEOUT if timeout is None else timeout

    try:
        with urllib.request.urlopen(request, timeout=request_timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise RuntimeError(f"Ollama request failed for model '{model}'") from exc

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
    response = client.models.generate_content(model=model, contents=prompt)
    text = response.text
    if not text:
        raise RuntimeError("Model returned an empty response")
    return text.strip()
