from pathlib import Path

from workspace_core.errors import WorkspaceError
from workspace_core.result import PathResult
from workspace_core.rules import DEFAULT_BLOCKED_NAMES


class Workspace:
    def __init__(
        self,
        root: str,
        read_only: bool = True,
        blocked_names: list[str] | None = None,
        blocked_paths: list[str] | None = None,
    ):
        self.root = Path(root).resolve()
        self.read_only = read_only
        self.blocked_names = set(blocked_names or DEFAULT_BLOCKED_NAMES)
        self.blocked_paths = [Path(p).as_posix().strip("/") for p in (blocked_paths or [])]

    def _check_blocked(self, rel_path: Path):
        parts = set(rel_path.parts)
        if any(name in parts for name in self.blocked_names):
            raise WorkspaceError("path_blocked", f"Blocked path segment in: {rel_path.as_posix()}")
        rel = rel_path.as_posix()
        if any(rel == bp or rel.startswith(bp + "/") for bp in self.blocked_paths if bp):
            raise WorkspaceError("path_blocked", f"Blocked path: {rel}")

    def resolve(self, path: str) -> str:
        candidate = (self.root / path).resolve()
        try:
            rel = candidate.relative_to(self.root)
        except ValueError as exc:
            raise WorkspaceError("path_outside_root", f"Path escapes root: {path}") from exc
        self._check_blocked(rel)
        return str(candidate)

    def validate(self, path: str) -> PathResult:
        try:
            return PathResult(ok=True, path=self.resolve(path), error=None)
        except WorkspaceError as exc:
            return PathResult(ok=False, path=None, error=f"{exc.code}: {exc.message}")

    def exists(self, path: str) -> bool:
        return Path(self.resolve(path)).exists()

    def is_file(self, path: str) -> bool:
        return Path(self.resolve(path)).is_file()

    def is_dir(self, path: str) -> bool:
        return Path(self.resolve(path)).is_dir()

    def read_text(self, path: str, max_chars: int = 20000) -> str:
        p = Path(self.resolve(path))
        if not p.exists():
            raise WorkspaceError("not_found", f"Path not found: {path}")
        if not p.is_file():
            raise WorkspaceError("not_file", f"Not a file: {path}")
        with p.open("r", encoding="utf-8", errors="replace") as f:
            return f.read(max_chars)

    def _check_writable(self):
        if self.read_only:
            raise WorkspaceError("read_only_violation", "Workspace is read-only")

    def write_text(self, path: str, content: str, overwrite: bool = False) -> None:
        self._check_writable()
        p = Path(self.resolve(path))
        p.parent.mkdir(parents=True, exist_ok=True)
        if p.exists() and not overwrite:
            raise WorkspaceError("path_blocked", f"File exists and overwrite is False: {path}")
        p.write_text(content, encoding="utf-8")

    def append_text(self, path: str, content: str) -> None:
        self._check_writable()
        p = Path(self.resolve(path))
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as f:
            f.write(content)

    def list_dir(self, path: str = ".") -> list[str]:
        p = Path(self.resolve(path))
        if not p.exists():
            raise WorkspaceError("not_found", f"Path not found: {path}")
        if not p.is_dir():
            raise WorkspaceError("not_dir", f"Not a directory: {path}")
        return sorted(item.name for item in p.iterdir())

    def safe_join(self, *parts: str) -> str:
        return self.resolve(str(Path(*parts)))
