"""How much of profitability is explained by what industry a company is in.

The received view is that margin is a sector property: you buy software for
software margins and you buy retail knowing you will not get them. This module
tests that against the data instead of assuming it, using a variance
decomposition rather than a comparison of medians — medians can differ by a lot
while explaining almost nothing, and that turns out to be roughly what happens.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from . import config
from .sectors import NON_OPERATING_MARGIN_SECTORS


def group_summary(df: pd.DataFrame, group: str, value: str,
                  min_n: int = config.MIN_GROUP_SIZE) -> pd.DataFrame:
    """Median, quartiles and spread per group, ordered by median.

    Medians and IQRs rather than means and standard deviations throughout: the
    margin distribution has a long right tail and a handful of REIT and
    semiconductor observations would otherwise set the level for their sector.
    """
    s = df[[group, value, "market_cap"]].dropna(subset=[value])
    out = (
        s.groupby(group)
        .agg(
            n=(value, "size"),
            median=(value, "median"),
            q1=(value, lambda x: x.quantile(0.25)),
            q3=(value, lambda x: x.quantile(0.75)),
            p10=(value, lambda x: x.quantile(0.10)),
            p90=(value, lambda x: x.quantile(0.90)),
            market_cap=("market_cap", "sum"),
        )
        .reset_index()
    )
    out["iqr"] = out["q3"] - out["q1"]
    out = out[out["n"] >= min_n].sort_values("median", ascending=False)
    return out.reset_index(drop=True)


def variance_decomposition(df: pd.DataFrame, group: str, value: str,
                           min_n: int = 3) -> dict:
    """One-way ANOVA with both the biased and the unbiased effect size.

    eta-squared is the share of total variance falling between groups. It is
    biased upward, and the bias grows with the number of groups — which matters
    enormously here, because the source's grouping column has 127 levels across
    503 rows. omega-squared corrects for that and is the number to quote when
    the group count is large relative to the sample:

        omega^2 = (SS_between - (k-1) * MS_within) / (SS_total + MS_within)

    Groups thinner than `min_n` are dropped from the test rather than pooled
    into an "other" bucket, because pooling unrelated thin industries creates a
    high-variance group that suppresses the between-group share.
    """
    s = df[[group, value]].dropna()
    groups = [g[value].to_numpy() for _, g in s.groupby(group) if len(g) >= min_n]
    if len(groups) < 2:
        raise ValueError(f"Not enough groups of size >= {min_n} for {group}")

    y = np.concatenate(groups)
    grand = y.mean()
    ss_total = ((y - grand) ** 2).sum()
    ss_between = sum(len(g) * (g.mean() - grand) ** 2 for g in groups)
    ss_within = ss_total - ss_between

    k, n = len(groups), len(y)
    ms_within = ss_within / (n - k)
    f_stat, p_value = stats.f_oneway(*groups)

    return {
        "grouping": group,
        "metric": value,
        "groups": int(k),
        "observations": int(n),
        "f_statistic": float(f_stat),
        "p_value": float(p_value),
        "eta_squared": float(ss_between / ss_total),
        "omega_squared": float(
            (ss_between - (k - 1) * ms_within) / (ss_total + ms_within)
        ),
        "share_within_group": float(ss_within / ss_total),
    }


def spread_comparison(summary: pd.DataFrame, df: pd.DataFrame, value: str) -> dict:
    """Spread inside a typical sector against spread across sector medians.

    This is the same question the variance decomposition answers, expressed in
    units a reader can price. If the median sector's interquartile range is
    wider than the interquartile range of the sector medians themselves, then
    knowing a company's sector tells you less about its margin than knowing
    where it sits within that sector.
    """
    y = df[value].dropna()
    return {
        "median_within_sector_iqr": float(summary["iqr"].median()),
        "iqr_of_sector_medians": float(
            summary["median"].quantile(0.75) - summary["median"].quantile(0.25)
        ),
        "full_sample_iqr": float(y.quantile(0.75) - y.quantile(0.25)),
        "range_of_sector_medians": float(
            summary["median"].max() - summary["median"].min()
        ),
        "widest_sector": str(summary.loc[summary["iqr"].idxmax(), summary.columns[0]]),
        "widest_sector_iqr": float(summary["iqr"].max()),
        "narrowest_sector": str(summary.loc[summary["iqr"].idxmin(), summary.columns[0]]),
        "narrowest_sector_iqr": float(summary["iqr"].min()),
    }


def run(margin_universe: pd.DataFrame, core_universe: pd.DataFrame) -> dict:
    """Full dispersion analysis, returning results and the tables to write out."""
    by_sector = group_summary(margin_universe, "sector", "ebitda_margin")
    by_subindustry = group_summary(margin_universe, "sub_industry", "ebitda_margin")
    net_by_sector = group_summary(core_universe, "sector", "net_margin")

    # Banks report interest income and REITs report rent against a depreciating
    # asset base, so neither "margin" means what it means for an operating
    # company. They are reported, then the test is re-run without them, because
    # leaving them in is the single biggest driver of the apparent sector effect.
    operating = margin_universe[
        ~margin_universe["sector"].isin(NON_OPERATING_MARGIN_SECTORS)
    ]

    return {
        "tables": {
            "ebitda_margin_by_sector": by_sector,
            "ebitda_margin_by_subindustry": by_subindustry,
            "net_margin_by_sector": net_by_sector,
        },
        "metrics": {
            "ebitda_margin_by_sector": variance_decomposition(
                margin_universe, "sector", "ebitda_margin"
            ),
            "ebitda_margin_by_subindustry": variance_decomposition(
                margin_universe, "sub_industry", "ebitda_margin"
            ),
            "net_margin_by_sector": variance_decomposition(
                core_universe, "sector", "net_margin"
            ),
            "ebitda_margin_by_sector_operating_only": variance_decomposition(
                operating, "sector", "ebitda_margin"
            ),
            "spread": spread_comparison(by_sector, margin_universe, "ebitda_margin"),
            "operating_universe_n": int(len(operating)),
        },
    }
