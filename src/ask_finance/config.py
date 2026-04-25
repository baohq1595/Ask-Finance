"""Paths and model settings. Resolves from repo root."""

from __future__ import annotations

import json
import os
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


REPO_ROOT = _repo_root()
DATA_DIR = REPO_ROOT / "data"
DEFAULT_SERVICE_ACCOUNT = REPO_ROOT / "authen" / "service-account.json"
LOGS_DIR = REPO_ROOT / "logs"


def _read_project_id_from_sa(path: Path) -> str | None:
    if not path.is_file():
        return None
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data.get("project_id")
    except (OSError, json.JSONDecodeError):
        return None


# Vertex: override with GOOGLE_CLOUD_PROJECT or GOOGLE_PROJECT_ID
GOOGLE_PROJECT_ID: str = (
    os.environ.get("GOOGLE_CLOUD_PROJECT")
    or os.environ.get("GOOGLE_PROJECT_ID")
    or _read_project_id_from_sa(DEFAULT_SERVICE_ACCOUNT)
    or ""
)
VERTEX_LOCATION: str = os.environ.get("VERTEX_LOCATION", "us-central1")
MODEL_NAME: str = os.environ.get("ASK_FINANCE_MODEL", "gemini-2.5-flash")

# Cost / verbosity caps (GenerateContentConfig)
MAX_OUTPUT_TOKENS: int = int(os.environ.get("ASK_FINANCE_MAX_OUTPUT_TOKENS", "4096"))
# Thinking: 0 disables extended thinking for supported models
THINKING_BUDGET: int = int(os.environ.get("ASK_FINANCE_THINKING_BUDGET", "0"))
AGENT_TEMPERATURE: float = float(os.environ.get("ASK_FINANCE_TEMPERATURE", "0.2"))
# Multi-turn cap (safety and cost for tool loops; agent-level)
MAX_AGENT_TURNS: int = int(os.environ.get("ASK_FINANCE_MAX_AGENT_TURNS", "12"))


def get_credentials_path() -> Path:
    p = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "")
    if p:
        return Path(p)
    return DEFAULT_SERVICE_ACCOUNT


def apply_credentials_env() -> Path:
    """Set GOOGLE_APPLICATION_CREDENTIALS to default JSON if not set. Returns path used."""
    path = get_credentials_path()
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(path.resolve())
    return path
