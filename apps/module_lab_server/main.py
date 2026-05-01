from __future__ import annotations
from typing import Any

try:
    from fastapi import FastAPI
except Exception:
    FastAPI = None  # type: ignore


def _build_result_payload(result: Any) -> dict[str, Any]:
    metadata = dict(getattr(result, "metadata", {}) or {})
    return {
        "text": getattr(result, "text", ""),
        "completed": bool(getattr(result, "completed", False)),
        "stop_reason": getattr(result, "stop_reason", None),
        "metadata": metadata,
    }


def _count_tool_traces(metadata: dict[str, Any]) -> int:
    traces = metadata.get("tool_traces")
    if isinstance(traces, list):
        return len(traces)
    events = metadata.get("events") or []
    if isinstance(events, list):
        return sum(1 for e in events if isinstance(e, dict) and e.get("type") == "tool_call")
    return 0


if FastAPI is not None:
    from fastapi.middleware.cors import CORSMiddleware
    from pydantic import BaseModel
    from agent_core import Agent, format_debug_report
    from llm_core import LLMClient

    app = FastAPI(title="Module Lab Server")
    app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

    class RunRequest(BaseModel):
        task: str
        model: str = "ollama:gemma:e2b"
        response_mode: str = "pipeline"
        execution_mode: str = "direct"
        max_rounds: int = 4
        max_actions: int = 10
        timeout: int = 600
        role: str | None = None
        persona: str | None = None
        enable_tracing: bool = True

    class DebugRequest(BaseModel):
        metadata: dict[str, Any]

    @app.get("/api/models")
    def models() -> dict[str, Any]:
        try:
            from model_router import list_models
            models = list_models()
            if models:
                return {"models": models}
        except Exception:
            pass
        return {"models": ["ollama:gemma:e2b"], "warning": "model_router.list_models unavailable; using default"}

    @app.post("/api/agent/run")
    def run_agent(req: RunRequest) -> dict[str, Any]:
        llm = LLMClient(model=req.model, timeout=req.timeout, enable_tracing=req.enable_tracing)
        agent = Agent(name="module_lab", role=req.role, persona=req.persona, model=req.model, response_mode=req.response_mode, execution_mode=req.execution_mode, max_rounds=req.max_rounds, max_actions=req.max_actions, timeout=req.timeout, llm=llm)
        result = agent.generate(req.task)
        payload = _build_result_payload(result)
        md = payload["metadata"]
        md["llm_traces"] = [t.__dict__ for t in llm.get_traces()]
        md["llm_traces_count"] = len(md["llm_traces"])
        md["tool_traces_count"] = _count_tool_traces(md)
        return payload

    @app.post("/api/debug/report")
    def debug_report(req: DebugRequest) -> dict[str, str]:
        return {"report": format_debug_report({"metadata": req.metadata})}
else:
    from flask import Flask, jsonify, request
    from flask_cors import CORS
    from agent_core import Agent, format_debug_report
    from llm_core import LLMClient

    app = Flask(__name__)
    CORS(app)

    @app.get("/api/models")
    def models():
        try:
            from model_router import list_models
            models = list_models()
            if models:
                return jsonify({"models": models})
        except Exception:
            pass
        return jsonify({"models": ["ollama:gemma:e2b"], "warning": "model_router.list_models unavailable; using default"})

    @app.post("/api/agent/run")
    def run_agent():
        req = request.get_json(force=True)
        llm = LLMClient(model=req.get("model", "ollama:gemma:e2b"), timeout=req.get("timeout", 600), enable_tracing=req.get("enable_tracing", True))
        agent = Agent(name="module_lab", role=req.get("role"), persona=req.get("persona"), model=req.get("model", "ollama:gemma:e2b"), response_mode=req.get("response_mode", "pipeline"), execution_mode=req.get("execution_mode", "direct"), max_rounds=req.get("max_rounds", 4), max_actions=req.get("max_actions", 10), timeout=req.get("timeout", 600), llm=llm)
        result = agent.generate(req.get("task", ""))
        payload = _build_result_payload(result)
        md = payload["metadata"]
        md["llm_traces"] = [t.__dict__ for t in llm.get_traces()]
        md["llm_traces_count"] = len(md["llm_traces"])
        md["tool_traces_count"] = _count_tool_traces(md)
        return jsonify(payload)

    @app.post("/api/debug/report")
    def debug_report():
        req = request.get_json(force=True)
        return jsonify({"report": format_debug_report({"metadata": req.get("metadata", {})})})
