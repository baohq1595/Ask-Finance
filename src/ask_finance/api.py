"""FastAPI backend for Ask Finance.

The Gradio UI talks to this service over HTTP rather than calling the agent or
the tool functions directly. Run with:

    uvicorn ask_finance.api:app --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from ask_finance import config
from ask_finance.agent import run_ask
from ask_finance.data_loaders import FinancialData, load_all
from ask_finance.fallback import build_fallback_trace
from ask_finance.logging_setup import setup_logging
from ask_finance.tools import TOOL_HANDLERS, TOOL_SPECS, dispatch_tool

logger = logging.getLogger("ask_finance.api")


class AskRequest(BaseModel):
    role: str = Field(..., description="Role to simulate (RBAC).")
    message: str = Field(..., description="User question in English.")
    enable_fallback: bool = Field(
        default=True,
        description="If the model returns no tool calls, run a deterministic tool by intent.",
    )


class AskResponse(BaseModel):
    answer: str
    tool_trace: list[dict[str, Any]]
    request_id: str | None = None
    latency_s: float | None = None
    fallback_used: bool = False


class ToolRequest(BaseModel):
    role: str
    args: dict[str, Any] = Field(default_factory=dict)


class ToolResponse(BaseModel):
    tool: str
    result: dict[str, Any]


class RolesResponse(BaseModel):
    roles: list[str]


app = FastAPI(title="Ask Finance API", version="0.1.0")

_fd: FinancialData | None = None


def _get_fd() -> FinancialData:
    global _fd
    if _fd is None:
        _fd = load_all()
    return _fd


@app.on_event("startup")
def _on_startup() -> None:
    setup_logging()
    try:
        config.apply_credentials_env()
    except OSError as e:
        logger.warning("Credentials: %s", e)
    try:
        _get_fd()
    except FileNotFoundError as e:
        logger.error(
            "Could not load data from %s: %s. "
            "Set ASK_FINANCE_DATA_DIR or launch from a directory that contains data/.",
            config.DATA_DIR,
            e,
        )
        raise
    logger.info(
        "API startup complete. data_dir=%s project=%s model=%s",
        config.DATA_DIR,
        config.GOOGLE_PROJECT_ID,
        config.MODEL_NAME,
    )


@app.get("/health")
def health() -> dict[str, Any]:
    fd = _get_fd()
    return {
        "status": "ok",
        "model": config.MODEL_NAME,
        "project": config.GOOGLE_PROJECT_ID,
        "data_dir": str(config.DATA_DIR),
        "roles": list((fd.rbac.get("roles") or {}).keys()),
        "tools": [s["name"] for s in TOOL_SPECS],
    }


@app.get("/roles", response_model=RolesResponse)
def get_roles() -> RolesResponse:
    fd = _get_fd()
    roles = list((fd.rbac.get("roles") or {}).keys()) or ["Group CFO"]
    return RolesResponse(roles=roles)


@app.get("/tools")
def list_tools() -> dict[str, Any]:
    return {"tools": TOOL_SPECS}


@app.post("/ask", response_model=AskResponse)
def ask(req: AskRequest) -> AskResponse:
    if not (req.message or "").strip():
        raise HTTPException(status_code=400, detail="message must not be empty")
    fd = _get_fd()
    out = run_ask(fd, req.role, req.message.strip())
    trace = out.get("tool_trace") or []
    answer = out.get("answer", "")
    fallback_used = False
    if not trace and req.enable_fallback:
        fb = build_fallback_trace(req.message, fd, req.role)
        if fb:
            trace = fb
            fallback_used = True
            answer = (
                f"{answer}\n\n(Used fallback finance tool execution for artifact generation.)"
            ).strip()
    return AskResponse(
        answer=answer,
        tool_trace=trace,
        request_id=out.get("request_id"),
        latency_s=out.get("latency_s"),
        fallback_used=fallback_used,
    )


@app.post("/tools/{name}", response_model=ToolResponse)
def call_tool(name: str, req: ToolRequest) -> ToolResponse:
    if name not in TOOL_HANDLERS:
        raise HTTPException(status_code=404, detail=f"Unknown tool: {name}")
    fd = _get_fd()
    result = dispatch_tool(name, fd, req.role, json.dumps(req.args or {}))
    return ToolResponse(tool=name, result=result)
