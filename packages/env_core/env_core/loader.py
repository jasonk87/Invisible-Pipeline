import os
from pathlib import Path

_LOADED = False


def env_path() -> Path:
    return Path(__file__).resolve().parent.parent / "env" / ".env"


def _parse_value(raw: str) -> str:
    val = raw.strip()
    if len(val) >= 2 and ((val[0] == '"' and val[-1] == '"') or (val[0] == "'" and val[-1] == "'")):
        return val[1:-1]
    return val


def ensure_env_loaded() -> None:
    global _LOADED
    if _LOADED:
        return

    path = env_path()
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if "=" not in stripped:
                continue
            key, value = stripped.split("=", 1)
            key = key.strip()
            if not key:
                continue
            os.environ.setdefault(key, _parse_value(value))
    _LOADED = True


def get_env(key: str, default: str | None = None) -> str | None:
    ensure_env_loaded()
    return os.environ.get(key, default)


def require_env(key: str) -> str:
    ensure_env_loaded()
    value = os.environ.get(key)
    if value:
        return value
    raise RuntimeError(f"Missing required environment variable: {key}")
