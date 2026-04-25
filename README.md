# Ask Finance (AI Agent Prototype)

Finance-domain AI agent demo using `gemini-2.5-flash`, mock SAP/HFM-like data, role-based access control (RBAC), and a Gradio UI.

## What this prototype covers

- English-only Q&A for finance prompts (P&L, opex variance, EBIT margin trend, project ROI trend).
- Mock data ingestion from `data/`.
- Simulated RBAC by role (`Group CFO`, `Electronics GM`, `APAC Analyst`).
- Explainable responses driven by tool outputs with data source citation.
- Export from latest run to Excel and PowerPoint.
- Structured logging for debugging in `logs/ask_finance.log`.

## Tech stack

- LLM: `gemini-2.5-flash` via `google-genai` + Vertex AI.
- App/UI: Gradio (`app.py`).
- Data layer: `pandas`.
- Optional exports: `openpyxl`, `python-pptx`.

## Project layout

- `app.py`: Gradio app entrypoint.
- `src/ask_finance/config.py`: model, token/thinking caps, env and paths.
- `src/ask_finance/gemini.py`: Vertex client and generation config.
- `src/ask_finance/agent.py`: multi-turn manual tool-calling loop.
- `src/ask_finance/tools.py`: whitelisted finance tools.
- `src/ask_finance/rbac.py`: role-based filtering.
- `src/ask_finance/data_loaders.py`: mock data loading.
- `src/ask_finance/logging_setup.py`: rotating logging setup.
- `data/`: synthetic datasets and role map.
- `docs/ARCHITECTURE.md`: architecture + evaluation strategy.

## Setup

1. Create and activate a virtual environment.
2. Install deps:
   - `pip install -r requirements.txt`
   - or `pip install -e .`
3. Ensure credentials are available:
   - default path: `authen/service-account.json`
   - or set `GOOGLE_APPLICATION_CREDENTIALS` to another path.

## Runtime config

Supported env vars:

- `GOOGLE_CLOUD_PROJECT` or `GOOGLE_PROJECT_ID`
- `VERTEX_LOCATION` (default `us-central1`)
- `ASK_FINANCE_MODEL` (default `gemini-2.5-flash`)
- `ASK_FINANCE_MAX_OUTPUT_TOKENS` (default `4096`)
- `ASK_FINANCE_THINKING_BUDGET` (default `0`)
- `ASK_FINANCE_TEMPERATURE` (default `0.2`)
- `ASK_FINANCE_MAX_AGENT_TURNS` (default `12`)

## Run

- `python app.py`
- Open the Gradio URL printed in terminal.

## Example prompts

- `What was our Opex variance for Q2 2024 in the Electronics division?`
- `Show me the ROI trend of Project Orion over the last 3 years.`
- `Summarize this month's P&L highlights for APAC.`

## Cost-control settings

The app caps generation cost/verbosity by:

- `max_output_tokens` (hard cap per model call),
- `thinking_budget` (set low/zero),
- `MAX_AGENT_TURNS` (caps tool-loop turns).

## Evaluation strategy (no unit tests in this phase)

This phase intentionally does **not** include automated unit tests.  
Evaluation is documented in `docs/ARCHITECTURE.md` as an AI/ML test plan:

- end-to-end golden scenarios,
- per-step model assessment (intent/tool-choice, numeric grounding, RBAC compliance, explanation quality),
- human scoring rubric and repeatability guidance.

