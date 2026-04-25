"""Load mock CSV/JSON into in-memory tables."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from ask_finance import config


@dataclass
class FinancialData:
    pl_monthly: pd.DataFrame
    budget_monthly: pd.DataFrame
    projects: pd.DataFrame
    rbac: dict

    def source_labels(self) -> dict[str, str]:
        return {
            "pl_monthly": "data/pl_monthly.csv (actuals)",
            "budget_monthly": "data/budget_monthly.csv (plan)",
            "projects": "data/projects.csv (projects / ROI)",
            "rbac": "data/rbac.json",
        }


def load_all(data_dir: Path | None = None) -> FinancialData:
    root = data_dir or config.DATA_DIR
    pl_path = root / "pl_monthly.csv"
    bud_path = root / "budget_monthly.csv"
    proj_path = root / "projects.csv"
    rbac_path = root / "rbac.json"

    pl_m = pd.read_csv(pl_path)
    bud = pd.read_csv(bud_path)
    proj = pd.read_csv(proj_path)
    with open(rbac_path, encoding="utf-8") as f:
        rbac = json.load(f)

    for df in (pl_m, bud, proj):
        for col in ("bu", "region", "currency"):
            if col in df.columns:
                df[col] = df[col].astype(str).str.strip()

    return FinancialData(
        pl_monthly=pl_m, budget_monthly=bud, projects=proj, rbac=rbac
    )
