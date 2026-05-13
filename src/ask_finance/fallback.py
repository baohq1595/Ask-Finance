"""Deterministic fallback executor: if the LLM does not request any tool, pick one by intent."""

from __future__ import annotations

import json
import re
from typing import Any

from ask_finance.data_loaders import FinancialData
from ask_finance.tools import (
    get_ebit_margin_trend,
    get_opex_variance,
    get_project_roi_trend,
)


def build_fallback_trace(
    message: str, fd: FinancialData, role: str
) -> list[dict[str, Any]]:
    """Return a single-step tool trace inferred from the question, or [] if nothing matches."""
    q = (message or "").lower()
    proj_years = sorted(
        fd.projects["reporting_year"].dropna().astype(int).unique().tolist()
    )
    pl_years = sorted(
        fd.pl_monthly["fiscal_year"].dropna().astype(int).unique().tolist()
    )
    latest_year = proj_years[-1] if proj_years else 2024
    start_default = latest_year - 2
    m_year = re.findall(r"\b(20\d{2})\b", q)
    if len(m_year) >= 2:
        start_y, end_y = int(m_year[0]), int(m_year[-1])
    elif len(m_year) == 1:
        end_y = int(m_year[0])
        start_y = end_y - 2
    else:
        start_y, end_y = start_default, latest_year

    if "roi" in q or "orion" in q:
        args = {"project_name": "Orion", "start_year": start_y, "end_year": end_y}
        return [
            {
                "tool": "get_project_roi_trend",
                "args": json.dumps(args),
                "result": get_project_roi_trend(fd, role, args),
                "s": 0.0,
            }
        ]

    q_match = re.search(r"\bq([1-4])\b", q)
    quarter = int(q_match.group(1)) if q_match else 2
    year_for_var = int(m_year[0]) if m_year else latest_year
    if "opex" in q and "variance" in q:
        bu = "Electronics" if "electronics" in q else None
        args: dict[str, Any] = {"fiscal_year": year_for_var, "quarter": quarter}
        if bu:
            args["bu"] = bu
        return [
            {
                "tool": "get_opex_variance",
                "args": json.dumps(args),
                "result": get_opex_variance(fd, role, args),
                "s": 0.0,
            }
        ]

    if "ebit" in q and "margin" in q:
        if pl_years:
            if "all years" in q or "all year" in q:
                start_y = pl_years[0]
                end_y = pl_years[-1]
            else:
                start_y = max(start_y, pl_years[0])
                end_y = min(end_y, pl_years[-1])
                if start_y > end_y:
                    start_y, end_y = pl_years[0], pl_years[-1]
        args = {"start_year": start_y, "end_year": end_y}
        if "electronics" in q:
            args["bu"] = "Electronics"
        return [
            {
                "tool": "get_ebit_margin_trend",
                "args": json.dumps(args),
                "result": get_ebit_margin_trend(fd, role, args),
                "s": 0.0,
            }
        ]
    return []
