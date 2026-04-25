"""Vertex Gemini client (google-genai), aligned with project reference: Client + GenerateContentConfig."""

from __future__ import annotations

import logging
import os
from typing import Any

from google import genai
from google.genai import types

from ask_finance import config
from ask_finance.tools import TOOL_SPECS

logger = logging.getLogger("ask_finance.gemini")

_client: genai.Client | None = None


def get_client() -> genai.Client:
    global _client
    if _client is not None:
        return _client
    path = config.apply_credentials_env()
    if not config.GOOGLE_PROJECT_ID:
        raise RuntimeError(
            "GOOGLE_PROJECT_ID / GOOGLE_CLOUD_PROJECT not set and could not read project_id from service account. "
            f"Checked credentials: {path}"
        )
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(path)
    _client = genai.Client(
        vertexai=True,
        project=config.GOOGLE_PROJECT_ID,
        location=config.VERTEX_LOCATION,
    )
    logger.info("GenAI client created for project %s, location %s", config.GOOGLE_PROJECT_ID, config.VERTEX_LOCATION)
    return _client


def _build_tool() -> types.Tool:
    decls: list[types.FunctionDeclaration] = []
    for spec in TOOL_SPECS:
        decls.append(
            types.FunctionDeclaration(
                name=spec["name"],
                description=spec["description"],
                parameters_json_schema=spec["parameters"],
            )
        )
    return types.Tool(function_declarations=decls)


def default_safety() -> list[types.SafetySetting]:
    # Match style used in project reference (string categories).
    b = "BLOCK_ONLY_HIGH"
    return [
        types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH", threshold=b),
        types.SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold=b),
        types.SafetySetting(category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold=b),
        types.SafetySetting(category="HARM_CATEGORY_HARASSMENT", threshold=b),
    ]


def make_generation_config(
    *,
    system_instruction: str,
    include_tools: bool = True,
) -> types.GenerateContentConfig:
    """Disables automatic function calling; agent loop runs tools and re-invokes the model."""
    return types.GenerateContentConfig(
        system_instruction=system_instruction,
        temperature=config.AGENT_TEMPERATURE,
        max_output_tokens=config.MAX_OUTPUT_TOKENS,
        safety_settings=default_safety(),
        tools=[_build_tool()] if include_tools else [],
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        thinking_config=types.ThinkingConfig(thinking_budget=config.THINKING_BUDGET),
    )


def generate_content(
    model: str,
    contents: list[types.Content],
    gen_config: types.GenerateContentConfig,
) -> Any:
    client = get_client()
    return client.models.generate_content(
        model=model,
        contents=contents,
        config=gen_config,
    )
