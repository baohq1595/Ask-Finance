"""Role-based filters for mock RBAC. Role is always applied server-side, not from model args alone."""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd

logger = logging.getLogger("ask_finance.rbac")


def get_role_config(rbac: dict[str, Any], role: str) -> dict[str, Any] | None:
    roles = rbac.get("roles") or {}
    return roles.get(role)


def _passes_filters(
    row: pd.Series,
    allowed_bu: list[str] | None,
    allowed_regions: list[str] | None,
) -> bool:
    if allowed_bu is not None and str(row.get("bu", "")) not in set(allowed_bu):
        return False
    if allowed_regions is not None and str(row.get("region", "")) not in set(
        allowed_regions
    ):
        return False
    return True


def filter_dataframe(
    df: pd.DataFrame,
    rbac: dict[str, Any],
    role: str,
    *,
    require_bu_region: bool = True,
) -> pd.DataFrame:
    """
    If role missing, return empty and log. Null allowed_bu / allowed_regions in JSON means "no filter".
    """
    rc = get_role_config(rbac, role)
    if not rc:
        logger.warning("Unknown role %r — no rows allowed.", role)
        return df.iloc[0:0].copy()
    ab = rc.get("allowed_bu")
    ar = rc.get("allowed_regions")
    if ab is not None:
        ab = [str(x).strip() for x in ab]
    if ar is not None:
        ar = [str(x).strip() for x in ar]
    if not require_bu_region and ("bu" not in df.columns or "region" not in df.columns):
        return df.copy()
    if df.empty:
        return df.copy()
    if ab is None and ar is None:
        return df.copy()
    mask = df.apply(
        lambda r: _passes_filters(
            r,
            ab,
            ar,
        ),
        axis=1,
    )
    return df.loc[mask].copy()
