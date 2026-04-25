"""Whitelisted tool implementations; RBAC applied with session role in the executor (not from model)."""

from __future__ import annotations

import json
import logging
from typing import Any

import pandas as pd

from ask_finance.data_loaders import FinancialData
from ask_finance.rbac import filter_dataframe

logger = logging.getLogger("ask_finance.tools")

TOOL_SPECS: list[dict[str, Any]] = [
    {
        "name": "list_accessible_scope",
        "description": "List business units and regions the current user can see (after role restrictions).",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_opex_variance",
        "description": "Opex actual vs plan variance for a fiscal year and quarter. Compares sum(opex) from P&L to sum(opex_plan) from budget for matching rows. Optional bu/region to narrow (must be within user access).",
        "parameters": {
            "type": "object",
            "properties": {
                "fiscal_year": {"type": "integer"},
                "quarter": {
                    "type": "integer",
                    "description": "Calendar quarter 1-4 (Q1=Jan-Mar, Q2=Apr-Jun, etc.)",
                },
                "bu": {
                    "type": "string",
                    "description": "Business unit name, e.g. Electronics",
                },
                "region": {"type": "string", "description": "e.g. APAC, EMEA"},
            },
            "required": ["fiscal_year", "quarter"],
        },
    },
    {
        "name": "get_ebit_margin_trend",
        "description": "EBIT margin by fiscal year: margin = sum(ebit)/sum(revenue) for rows in range. Use for EBIT margin trend questions.",
        "parameters": {
            "type": "object",
            "properties": {
                "start_year": {"type": "integer"},
                "end_year": {"type": "integer"},
                "bu": {"type": "string"},
                "region": {"type": "string"},
            },
            "required": ["start_year", "end_year"],
        },
    },
    {
        "name": "get_pl_summary",
        "description": "Sum revenue, cogs, opex, ebit for optional filters. For P&L highlights or month-level rollups.",
        "parameters": {
            "type": "object",
            "properties": {
                "fiscal_year": {"type": "integer"},
                "month": {
                    "type": "integer",
                    "description": "1-12, optional if full year",
                },
                "quarter": {"type": "integer"},
                "bu": {"type": "string"},
                "region": {"type": "string"},
            },
            "required": ["fiscal_year"],
        },
    },
    {
        "name": "get_project_roi_trend",
        "description": "Project Orion or other projects: ROI trend as benefit/investment by reporting year. Filter by project name (partial match ok).",
        "parameters": {
            "type": "object",
            "properties": {
                "project_name": {"type": "string"},
                "start_year": {"type": "integer"},
                "end_year": {"type": "integer"},
            },
            "required": ["project_name", "start_year", "end_year"],
        },
    },
]


def _pl_filtered(fd: FinancialData, role: str) -> pd.DataFrame:
    return filter_dataframe(fd.pl_monthly, fd.rbac, role)


def _bud_filtered(fd: FinancialData, role: str) -> pd.DataFrame:
    return filter_dataframe(fd.budget_monthly, fd.rbac, role)


def _proj_filtered(fd: FinancialData, role: str) -> pd.DataFrame:
    return filter_dataframe(fd.projects, fd.rbac, role)


def _months_for_quarter(quarter: int) -> list[int]:
    if quarter == 1:
        return [1, 2, 3]
    if quarter == 2:
        return [4, 5, 6]
    if quarter == 3:
        return [7, 8, 9]
    if quarter == 4:
        return [10, 11, 12]
    return []


def list_accessible_scope(
    fd: FinancialData, role: str, _args: dict[str, Any]
) -> dict[str, Any]:
    p = _pl_filtered(fd, role)
    if p.empty:
        return {
            "business_units": [],
            "regions": [],
            "sources": ["pl_monthly (empty after RBAC)"],
        }
    bus = sorted(p["bu"].dropna().unique().tolist())
    reg = sorted(p["region"].dropna().unique().tolist())
    return {
        "business_units": bus,
        "regions": reg,
        "role": role,
        "sources": ["data/pl_monthly.csv"],
    }


def get_opex_variance(
    fd: FinancialData, role: str, args: dict[str, Any]
) -> dict[str, Any]:
    fy = int(args["fiscal_year"])
    q = int(args["quarter"])
    bu = args.get("bu")
    region = args.get("region")
    months = _months_for_quarter(q)
    if not months:
        return {
            "error": "quarter must be 1-4",
            "sources": [],
        }

    pls = _pl_filtered(fd, role)
    bds = _bud_filtered(fd, role)
    pls = pls[pls["fiscal_year"] == fy]
    pls = pls[pls["month"].isin(months)]
    bds = bds[bds["fiscal_year"] == fy]
    bds = bds[bds["month"].isin(months)]
    if bu:
        pls = pls[pls["bu"] == bu]
        bds = bds[bds["bu"] == bu]
    if region:
        pls = pls[pls["region"] == region]
        bds = bds[bds["region"] == region]

    opex_actual = float(pls["opex"].sum()) if not pls.empty else 0.0
    opex_plan = float(bds["opex_plan"].sum()) if not bds.empty else 0.0
    var_abs = opex_actual - opex_plan
    var_pct = (var_abs / opex_plan * 100) if opex_plan else None

    return {
        "fiscal_year": fy,
        "quarter": q,
        "filters": {k: v for k, v in {"bu": bu, "region": region}.items() if v},
        "opex_actual_sum": round(opex_actual, 4),
        "opex_plan_sum": round(opex_plan, 4),
        "variance_amount": round(var_abs, 4),
        "variance_pct": round(var_pct, 2) if var_pct is not None else None,
        "row_count_pl": int(len(pls)),
        "row_count_budget": int(len(bds)),
        "sources": [
            "data/pl_monthly.csv (opex actuals)",
            "data/budget_monthly.csv (opex_plan)",
        ],
    }


def get_ebit_margin_trend(
    fd: FinancialData, role: str, args: dict[str, Any]
) -> dict[str, Any]:
    y0, y1 = int(args["start_year"]), int(args["end_year"])
    bu, region = args.get("bu"), args.get("region")
    p = _pl_filtered(fd, role)
    if p.empty:
        return {
            "start_year": y0,
            "end_year": y1,
            "requested_start_year": y0,
            "requested_end_year": y1,
            "filters": {k: v for k, v in {"bu": bu, "region": region}.items() if v},
            "by_fiscal_year": [],
            "sources": ["data/pl_monthly.csv"],
            "note": "no rows after RBAC filter",
        }

    min_year = int(p["fiscal_year"].min())
    max_year = int(p["fiscal_year"].max())
    # Clamp requested range to available data years.
    y0 = max(y0, min_year)
    y1 = min(y1, max_year)
    if y0 > y1:
        y0, y1 = min_year, max_year

    p = p[(p["fiscal_year"] >= y0) & (p["fiscal_year"] <= y1)]
    if bu:
        p = p[p["bu"] == bu]
    if region:
        p = p[p["region"] == region]
    years = sorted(p["fiscal_year"].dropna().unique().tolist()) if not p.empty else []
    by_year: list[dict[str, Any]] = []
    for y in years:
        sub = p[p["fiscal_year"] == y]
        rev = float(sub["revenue"].sum())
        e = float(sub["ebit"].sum())
        m = (e / rev) if rev else 0.0
        by_year.append(
            {
                "fiscal_year": int(y),
                "revenue_sum": round(rev, 4),
                "ebit_sum": round(e, 4),
                "ebit_margin": round(m, 4),
            }
        )
    return {
        "start_year": y0,
        "end_year": y1,
        "requested_start_year": int(args["start_year"]),
        "requested_end_year": int(args["end_year"]),
        "available_data_years": [min_year, max_year],
        "filters": {k: v for k, v in {"bu": bu, "region": region}.items() if v},
        "by_fiscal_year": by_year,
        "sources": ["data/pl_monthly.csv"],
    }


def get_pl_summary(
    fd: FinancialData, role: str, args: dict[str, Any]
) -> dict[str, Any]:
    fy = int(args["fiscal_year"])
    p = _pl_filtered(fd, role)
    p = p[p["fiscal_year"] == fy]
    if "month" in args and args["month"] is not None:
        p = p[p["month"] == int(args["month"])]
    if "quarter" in args and args.get("quarter") is not None:
        mlist = _months_for_quarter(int(args["quarter"]))
        p = p[p["month"].isin(mlist)]
    if args.get("bu"):
        p = p[p["bu"] == args["bu"]]
    if args.get("region"):
        p = p[p["region"] == args["region"]]
    if p.empty:
        return {
            "fiscal_year": fy,
            "filters": {k: args.get(k) for k in ("month", "quarter", "bu", "region") if args.get(k) is not None},
            "revenue": 0,
            "cogs": 0,
            "opex": 0,
            "ebit": 0,
            "ebit_margin": 0.0,
            "sources": ["data/pl_monthly.csv"],
            "note": "no rows (check filters or role)",
        }
    r = float(p["revenue"].sum())
    c = float(p["cogs"].sum())
    o = float(p["opex"].sum())
    e = float(p["ebit"].sum())
    m = (e / r) if r else 0.0
    return {
        "fiscal_year": fy,
        "filters": {k: args.get(k) for k in ("month", "quarter", "bu", "region") if args.get(k) is not None},
        "revenue": round(r, 4),
        "cogs": round(c, 4),
        "opex": round(o, 4),
        "ebit": round(e, 4),
        "ebit_margin": round(m, 4),
        "row_count": int(len(p)),
        "sources": ["data/pl_monthly.csv"],
    }


def get_project_roi_trend(
    fd: FinancialData, role: str, args: dict[str, Any]
) -> dict[str, Any]:
    name = (args.get("project_name") or "").strip()
    y0, y1 = int(args["start_year"]), int(args["end_year"])
    pr = _proj_filtered(fd, role)
    if name:
        pr = pr[pr["name"].str.contains(name, case=False, na=False)]
    pr = pr[(pr["reporting_year"] >= y0) & (pr["reporting_year"] <= y1)]
    pr = pr.sort_values("reporting_year")
    rows: list[dict[str, Any]] = []
    for _, r in pr.iterrows():
        inv = float(r["cumulative_investment_musd"])
        ben = float(r["cumulative_benefit_musd"])
        roi = (ben / inv) if inv else 0.0
        rows.append(
            {
                "project_id": r["project_id"],
                "name": r["name"],
                "bu": r["bu"],
                "region": r["region"],
                "reporting_year": int(r["reporting_year"]),
                "cumulative_investment_musd": round(inv, 4),
                "cumulative_benefit_musd": round(ben, 4),
                "cumulative_roi": round(roi, 4),
            }
        )
    return {
        "filter_name": name,
        "start_year": y0,
        "end_year": y1,
        "rows": rows,
        "sources": ["data/projects.csv"],
    }


TOOL_HANDLERS = {
    "list_accessible_scope": list_accessible_scope,
    "get_opex_variance": get_opex_variance,
    "get_ebit_margin_trend": get_ebit_margin_trend,
    "get_pl_summary": get_pl_summary,
    "get_project_roi_trend": get_project_roi_trend,
}


def dispatch_tool(
    name: str,
    fd: FinancialData,
    role: str,
    args_json: str,
) -> dict[str, Any]:
    if name not in TOOL_HANDLERS:
        return {"error": f"Unknown tool: {name}", "sources": []}
    try:
        args = json.loads(args_json) if args_json else {}
    except json.JSONDecodeError as e:
        return {"error": f"Invalid tool args JSON: {e}", "sources": []}
    handler = TOOL_HANDLERS[name]
    try:
        return handler(fd, role, args)
    except Exception as e:
        logger.exception("Tool %s failed: %s", name, e)
        return {"error": str(e), "sources": []}
