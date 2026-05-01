import json
import sys
from pathlib import Path


def _truncate(text, max_chars=4000):
    s = "" if text is None else str(text)
    return s if len(s) <= max_chars else s[:max_chars] + "...[truncated]"


def format_debug_report(result) -> str:
    md = getattr(result, "metadata", None)
    events = getattr(result, "events", None)
    completed = getattr(result, "completed", None)
    stop_reason = getattr(result, "stop_reason", None)

    if isinstance(result, dict):
        md = result.get("metadata", result)
        events = result.get("events")
        completed = result.get("completed", completed)
        stop_reason = result.get("stop_reason", stop_reason)

    md = md or {}
    lines = ["SUMMARY", f"- completed: {completed}", f"- stop_reason: {stop_reason}"]
    if "session_id" in md:
        lines.append(f"- session_id: {md.get('session_id')}")

    evs = events or md.get("events") or []
    if evs:
        lines.extend(["", "EVENTS"])
        for ev in evs:
            if isinstance(ev, dict):
                lines.append(f"[{ev.get('type', 'event')}] {ev.get('title', '')}")

    acts = md.get("activity_log") or []
    if acts:
        lines.extend(["", "TEAM ACTIVITY"])
        for a in acts:
            lines.append(f"- {a.get('agent', 'agent')}: {a.get('summary', '')}")

    traces = md.get("llm_traces") or []
    if traces:
        lines.extend(["", "LLM TRACES"])
        for i, entry in enumerate(traces, 1):
            agent = entry.get("agent") if isinstance(entry, dict) else None
            tr = entry.get("trace") if isinstance(entry, dict) and "trace" in entry else entry
            model = getattr(tr, "model", None) if not isinstance(tr, dict) else tr.get("model")
            dur = getattr(tr, "duration_ms", None) if not isinstance(tr, dict) else tr.get("duration_ms")
            err = getattr(tr, "error", None) if not isinstance(tr, dict) else tr.get("error")
            prompt = getattr(tr, "prompt", None) if not isinstance(tr, dict) else tr.get("prompt")
            response = getattr(tr, "response", None) if not isinstance(tr, dict) else tr.get("response")
            lines.extend([f"LLM CALL {i}", f"Agent: {agent}", f"Model: {model}", f"Duration: {dur} ms", f"Error: {err}", "", "PROMPT:", _truncate(prompt), "", "RESPONSE:", _truncate(response), ""])

    ttraces = md.get("tool_traces") or []
    if ttraces:
        lines.extend(["", "TOOL TRACES"])
        for i, t in enumerate(ttraces, 1):
            lines.extend([f"TOOL CALL {i}", f"Agent: {t.get('agent')}", f"Tool: {t.get('tool_name')}", f"Duration: {t.get('duration_ms')} ms", f"Args: {t.get('args')}", ""])

    return "\n".join(lines)


def _main(argv=None):
    argv = argv or sys.argv[1:]
    if not argv:
        print("Usage: python -m agent_core.debug_viewer path/to/debug.json", file=sys.stderr)
        return 2
    path = Path(argv[0])
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        print(f"Error: file not found: {path}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Error: invalid JSON: {exc}", file=sys.stderr)
        return 1
    print(format_debug_report(data))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
