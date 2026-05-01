from pathlib import Path

from repo_tools.types import FileInfo

DEFAULT_PATTERNS = ["*.py", "*.ts", "*.tsx", "*.js", "*.jsx", "*.json", "*.md", "*.toml", "*.yaml", "*.yml"]
DEFAULT_IGNORE_DIRS = [".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build", ".pytest_cache"]


def find_files(
    root: str = ".",
    patterns: list[str] | None = None,
    ignore_dirs: list[str] | None = None,
    max_files: int = 500,
) -> list[FileInfo]:
    root_path = Path(root)
    patt = patterns or DEFAULT_PATTERNS
    ignored = set(ignore_dirs or DEFAULT_IGNORE_DIRS)

    results: list[FileInfo] = []
    for path in root_path.rglob("*"):
        if len(results) >= max_files:
            break
        if path.is_dir():
            continue
        if any(part in ignored for part in path.parts):
            continue
        if not any(path.match(pattern) for pattern in patt):
            continue
        rel = path.relative_to(root_path).as_posix()
        results.append(FileInfo(path=rel, size_bytes=path.stat().st_size))

    results.sort(key=lambda x: x.path)
    return results[:max_files]


def read_text(path: str, max_chars: int = 20000) -> str:
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read(max_chars)


def tree_summary(root: str = ".", max_files: int = 200) -> str:
    rows = [f"- {f.path} ({f.size_bytes} bytes)" for f in find_files(root=root, max_files=max_files)]
    return "\n".join(rows)
