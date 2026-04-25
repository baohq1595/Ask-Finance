"""Multi-turn agent: manual function calling (AFC off) so tools run with server-side role."""

from __future__ import annotations

import json
import logging
import time
import uuid
from typing import Any

from google.genai import types

from ask_finance import config
from ask_finance.data_loaders import FinancialData
from ask_finance.gemini import generate_content, make_generation_config
from ask_finance.tools import dispatch_tool

logger = logging.getLogger("ask_finance.agent")

SYSTEM_TEMPLATE = """You are "Ask Finance", an English-only finance assistant for a conglomerate.
You answer using ONLY the provided tools and the numbers they return. Never invent figures.
The user's role is fixed for this session: {role}. Tools already enforce data access for that role — do not claim access outside it.
Glossary: P&L (revenue, COGS, opex, EBIT), EBIT margin = EBIT / revenue; opex variance = actual opex minus plan opex for the same period; ROI here = cumulative benefit / cumulative investment (from project data) when applicable.
When you answer:
- State the time period and filters you used.
- Cite which files the tools reference (see "sources" in tool output).
- If a tool returns an error or empty rows, say so clearly.
End with a short "Sources:" line listing dataset names from the last tool responses."""


def _fc_args_to_json(args: Any) -> str:
    if args is None:
        return "{}"
    if isinstance(args, str):
        return args
    if isinstance(args, dict):
        return json.dumps(args)
    # google.genai may return Struct-like
    try:
        return json.dumps(dict(args))
    except Exception:
        return json.dumps({})


def _parts_function_calls(response: Any) -> list[tuple[str, str, str | None]]:
    """List of (name, args_json, call_id) from first candidate."""
    out: list[tuple[str, str, str | None]] = []
    if not response.candidates:
        return out
    c0 = response.candidates[0]
    content = getattr(c0, "content", None) or c0
    parts = getattr(content, "parts", None) or []
    for p in parts:
        fc = getattr(p, "function_call", None)
        if fc is not None:
            name = getattr(fc, "name", None) or ""
            args = getattr(fc, "args", None)
            call_id = getattr(fc, "id", None)
            out.append((name, _fc_args_to_json(args), call_id))
    return out


def _response_text_or_empty(response: Any) -> str:
    t = getattr(response, "text", None)
    if t:
        return t
    if not response.candidates:
        return ""
    c0 = response.candidates[0]
    content = getattr(c0, "content", None) or c0
    parts = getattr(content, "parts", None) or []
    chunks: list[str] = []
    for p in parts:
        tx = getattr(p, "text", None)
        if tx:
            chunks.append(tx)
    return "".join(chunks)


def run_ask(
    financial_data: FinancialData,
    role: str,
    user_message: str,
) -> dict[str, Any]:
    """
    Returns { answer, tool_trace, request_id, latency_s }.
    """
    request_id = str(uuid.uuid4())[:8]
    system_instruction = SYSTEM_TEMPLATE.format(role=role)
    base_config = make_generation_config(system_instruction=system_instruction, include_tools=True)

    contents: list[types.Content] = [
        types.Content(
            role="user",
            parts=[types.Part(text=f"[User role: {role}]\n\n{user_message}")],
        )
    ]

    tool_trace: list[dict[str, Any]] = []
    t0 = time.perf_counter()

    for turn in range(config.MAX_AGENT_TURNS):
        logger.info(
            "request %s turn %s role=%s", request_id, turn, role
        )
        try:
            response = generate_content(
                config.MODEL_NAME,
                contents=contents,
                gen_config=base_config,
            )
        except Exception as e:
            logger.exception("request %s generate failed: %s", request_id, e)
            return {
                "answer": f"Model call failed: {e}",
                "tool_trace": tool_trace,
                "request_id": request_id,
                "latency_s": round(time.perf_counter() - t0, 3),
            }

        calls = _parts_function_calls(response)
        if not calls:
            text = _response_text_or_empty(response)
            if not text.strip():
                text = "The model did not return text. Try rephrasing or check logs for safety blocks."
            return {
                "answer": text.strip(),
                "tool_trace": tool_trace,
                "request_id": request_id,
                "latency_s": round(time.perf_counter() - t0, 3),
            }

        # Append model message that requested tool calls, then our function results.
        m_content = None
        if response.candidates:
            m_content = response.candidates[0].content
        if m_content is not None:
            contents.append(m_content)

        fr_parts: list[types.Part] = []
        for name, args_json, call_id in calls:
            if not name:
                continue
            t_tool0 = time.perf_counter()
            result = dispatch_tool(name, financial_data, role, args_json)
            tool_trace.append(
                {
                    "tool": name,
                    "args": args_json,
                    "result": result,
                    "s": round(time.perf_counter() - t_tool0, 4),
                }
            )
            logger.info("request %s tool=%s", request_id, name)
            fr = types.FunctionResponse(
                name=name,
                id=call_id,
                response=result,
            )
            fr_parts.append(types.Part(function_response=fr))

        contents.append(types.Content(role="user", parts=fr_parts))

    return {
        "answer": f"Stopped after {config.MAX_AGENT_TURNS} turns (safety cap).",
        "tool_trace": tool_trace,
        "request_id": request_id,
        "latency_s": round(time.perf_counter() - t0, 3),
    }
