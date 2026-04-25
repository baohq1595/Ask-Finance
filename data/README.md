# Mock data (synthetic) — “Ask Finance”

All amounts are **fictional** and for demo only.

| File | Purpose |
|------|---------|
| `pl_monthly.csv` | Monthly P&amp;L **actuals**: `revenue`, `cogs`, `opex`, `ebit` (USD) by `fiscal_year`, `month`, `quarter`, `bu`, `region`. |
| `budget_monthly.csv` | Same grain as plan: `revenue_plan`, `opex_plan` for variance (actuals come from `pl_monthly` joined on keys). |
| `projects.csv` | Project name **Orion** and others: `cumulative_investment_musd`, `cumulative_benefit_musd` by `reporting_year` for ROI / trend. |
| `rbac.json` | Role → `allowed_bu` / `allowed_regions` (null = no filter on that dimension). |

**Join key** for P&amp;L vs budget: `fiscal_year` + `month` + `bu` + `region` + `currency` (or string match on the first four where currency is always USD in mock data).

**Example queries supported by the mock sets**

- *Opex variance for Q2 in the Electronics division* — compare sum of `opex` (pl) to sum of `opex_plan` (budget) for `bu=Electronics`, `quarter=2` (or months 4–6).
- *ROI trend of Project Orion over the last 3 years* — filter `name=Orion`, use rows for 2021–2023 (or 2022–2024) and cumulative or derived ROI = benefit / investment.
- *P&amp;L highlights* — roll up `revenue` / `ebit` from `pl_monthly` for a `region` or `bu`.

## Roles (`rbac.json`)

- **Group CFO** — all BUs and regions.  
- **Electronics GM** — `Electronics` BU only.  
- **APAC Analyst** — `APAC` region only.
