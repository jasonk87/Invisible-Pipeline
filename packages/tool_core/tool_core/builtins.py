import re

from tool_core.types import Tool, ToolResult


def _missing_repo_tools() -> ToolResult:
    return ToolResult(ok=False, error="repo_tools is not installed")


def tree_summary_tool() -> Tool:
    def handler(root: str = ".") -> ToolResult:
        try:
            from repo_tools import tree_summary
        except ImportError:
            return _missing_repo_tools()
        return ToolResult(ok=True, output=tree_summary(root=root))

    return Tool(name="tree_summary", description="Summarize repository tree with file sizes", parameters={"root": {"type": "string"}}, handler=handler, risk="safe")


def read_text_tool() -> Tool:
    def handler(path: str, max_chars: int = 20000) -> ToolResult:
        try:
            from repo_tools import read_text
        except ImportError:
            return _missing_repo_tools()
        return ToolResult(ok=True, output=read_text(path=path, max_chars=max_chars))

    return Tool(name="read_text", description="Read UTF-8 text file", parameters={"path": {"type": "string"}, "max_chars": {"type": "integer"}}, handler=handler, risk="safe")


def find_files_tool() -> Tool:
    def handler(root: str = ".", max_files: int = 500) -> ToolResult:
        try:
            from repo_tools import find_files
        except ImportError:
            return _missing_repo_tools()
        files = find_files(root=root, max_files=max_files)
        return ToolResult(ok=True, output="\n".join(f.path for f in files))

    return Tool(name="find_files", description="Find files by patterns", parameters={"root": {"type": "string"}, "max_files": {"type": "integer"}}, handler=handler, risk="safe")


def command_fact_tool() -> Tool:
    def handler(command: list[str], cwd: str | None = None, timeout: int = 60) -> ToolResult:
        try:
            from repo_tools import command_fact
        except ImportError:
            return _missing_repo_tools()
        return ToolResult(ok=True, output=command_fact(command=command, cwd=cwd, timeout=timeout))

    return Tool(name="command_fact", description="Run command and return structured output fact", parameters={"command": {"type": "array"}, "cwd": {"type": "string"}, "timeout": {"type": "integer"}}, handler=handler, risk="safe")


def _require_workspace_core():
    try:
        from workspace_core import WorkspaceError
    except ImportError as exc:
        raise RuntimeError("workspace_core is not installed") from exc
    return WorkspaceError


def read_file_tool(workspace) -> Tool:
    WorkspaceError = _require_workspace_core()

    def handler(path: str, max_chars: int | None = None) -> ToolResult:
        try:
            text = workspace.read_text(path, max_chars=max_chars or 20000)
            return ToolResult(ok=True, output=text)
        except WorkspaceError as exc:
            return ToolResult(ok=False, error=str(exc))

    return Tool(name="read_file", description="Read file through workspace boundary", parameters={"path": {"type": "string"}, "max_chars": {"type": "integer"}}, handler=handler, risk="safe")


def write_file_tool(workspace) -> Tool:
    WorkspaceError = _require_workspace_core()

    def handler(path: str, content: str, overwrite: bool = False) -> ToolResult:
        try:
            workspace.write_text(path, content, overwrite=overwrite or False)
            return ToolResult(ok=True, output=f"Wrote file: {path}")
        except WorkspaceError as exc:
            return ToolResult(ok=False, error=str(exc))

    return Tool(name="write_file", description="Write file through workspace boundary", parameters={"path": {"type": "string"}, "content": {"type": "string"}, "overwrite": {"type": "boolean"}}, handler=handler, risk="write")


def append_file_tool(workspace) -> Tool:
    WorkspaceError = _require_workspace_core()

    def handler(path: str, content: str) -> ToolResult:
        try:
            workspace.append_text(path, content)
            return ToolResult(ok=True, output=f"Appended file: {path}")
        except WorkspaceError as exc:
            return ToolResult(ok=False, error=str(exc))

    return Tool(name="append_file", description="Append file through workspace boundary", parameters={"path": {"type": "string"}, "content": {"type": "string"}}, handler=handler, risk="write")


def _dominant_line_ending(text: str) -> str:
    crlf = text.count("\r\n")
    lf = text.count("\n") - crlf
    return "\r\n" if crlf > lf else "\n"


def _normalize_line_endings(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _whitespace_regex(search: str) -> re.Pattern[str]:
    normalized = _normalize_line_endings(search)
    parts = re.split(r"[ \t\n\r]+", normalized.strip())
    escaped = [re.escape(p) for p in parts if p]
    pattern = r"[ \t\r\n]+".join(escaped)
    return re.compile(pattern)


def apply_patch_tool(workspace) -> Tool:
    WorkspaceError = _require_workspace_core()

    def handler(path: str, search: str, replace: str, dry_run: bool = True, match_mode: str = "exact") -> ToolResult:
        if match_mode not in {"exact", "line_endings", "whitespace"}:
            return ToolResult(ok=False, error="invalid match_mode")

        try:
            original = workspace.read_text(path, max_chars=5_000_000)
        except WorkspaceError as exc:
            return ToolResult(ok=False, error=str(exc))

        try:
            if match_mode == "exact":
                matches = original.count(search)
                if matches == 0:
                    return ToolResult(ok=False, error="search block not found", metadata={"matches": 0})
                if matches > 1:
                    return ToolResult(ok=False, error="multiple search block matches found", metadata={"matches": matches})
                patched = original.replace(search, replace, 1)
            elif match_mode == "line_endings":
                nl = _dominant_line_ending(original)
                src_n = _normalize_line_endings(original)
                search_n = _normalize_line_endings(search)
                replace_n = _normalize_line_endings(replace)
                matches = src_n.count(search_n)
                if matches == 0:
                    return ToolResult(ok=False, error="search block not found", metadata={"matches": 0})
                if matches > 1:
                    return ToolResult(ok=False, error="multiple search block matches found", metadata={"matches": matches})
                patched_n = src_n.replace(search_n, replace_n, 1)
                patched = patched_n.replace("\n", nl)
            else:
                regex = _whitespace_regex(search)
                found = list(regex.finditer(original))
                matches = len(found)
                if matches == 0:
                    return ToolResult(ok=False, error="search block not found", metadata={"matches": 0})
                if matches > 1:
                    return ToolResult(ok=False, error="multiple search block matches found", metadata={"matches": matches})
                m = found[0]
                patched = original[: m.start()] + replace + original[m.end() :]
        except Exception as exc:
            return ToolResult(ok=False, error=f"patch failure: {exc}")

        if dry_run:
            return ToolResult(ok=True, output="Patch dry run succeeded", metadata={"matches": 1, "dry_run": True})

        try:
            workspace.write_text(path, patched, overwrite=True)
        except WorkspaceError as exc:
            return ToolResult(ok=False, error=str(exc))

        return ToolResult(ok=True, output=f"Patch applied: {path}", metadata={"matches": 1, "dry_run": False})

    return Tool(name="apply_patch", description="Apply a strict single-match patch through workspace boundary", parameters={"path": {"type": "string"}, "search": {"type": "string"}, "replace": {"type": "string"}, "dry_run": {"type": "boolean"}, "match_mode": {"type": "string"}}, handler=handler, risk="write")
