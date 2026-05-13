"""Paths and model settings.

Path resolution order (works whether the package is run editable from ``src/``
or installed into site-packages):

1. Explicit env var (``ASK_FINANCE_DATA_DIR``, ``ASK_FINANCE_LOGS_DIR``,
   ``ASK_FINANCE_REPO_ROOT``).
2. Walk up from this file looking for a directory that contains ``data/``
   (handles ``src/ask_finance/config.py`` editable installs).
3. ``Path.cwd()`` — useful when launching ``uvicorn`` from the repo root with
   the package installed non-editable.
"""

from __future__ import annotations

import json
import os
from pathlib import Path


def _env_path(name: str) -> Path | None:
    v = os.environ.get(name)
    if not v:
        return None
    return Path(v).expanduser().resolve()


def _find_repo_root() -> Path:
    env = _env_path("ASK_FINANCE_REPO_ROOT")
    if env and env.is_dir():
        return env
    here = Path(__file__).resolve()
    for parent in [here.parent, *here.parents]:
        if (parent / "data").is_dir():
            return parent
    cwd = Path.cwd().resolve()
    if (cwd / "data").is_dir():
        return cwd
    return here.parents[2] if len(here.parents) >= 3 else cwd


REPO_ROOT = _find_repo_root()


def _resolve_data_dir() -> Path:
    env = _env_path("ASK_FINANCE_DATA_DIR")
    if env:
        return env
    candidates = [
        REPO_ROOT / "data",
        Path.cwd() / "data",
    ]
    for c in candidates:
        if c.is_dir():
            return c.resolve()
    return candidates[0]


def _resolve_logs_dir() -> Path:
    env = _env_path("ASK_FINANCE_LOGS_DIR")
    if env:
        return env
    return (REPO_ROOT / "logs").resolve()


DATA_DIR = _resolve_data_dir()
LOGS_DIR = _resolve_logs_dir()
DEFAULT_SERVICE_ACCOUNT = (REPO_ROOT / "authen" / "service-account.json").resolve()


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


def apply_credentials_env() -> Path | None:
    """Point GOOGLE_APPLICATION_CREDENTIALS at the local service account JSON when it exists.

    Returns the path that was applied, or ``None`` if no file is present. In hosted
    environments (e.g. Cloud Run) the platform supplies Application Default
    Credentials, so leaving the env var unset is the correct behavior.
    """
    explicit = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "")
    if explicit:
        return Path(explicit)
    path = get_credentials_path()
    if path.is_file():
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(path.resolve())
        return path
    return None
