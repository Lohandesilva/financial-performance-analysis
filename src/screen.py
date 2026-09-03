"""Two screens: growth the balance sheet can fund against growth the price needs,
and a peer ranking inside the largest sector.

The growth screen is the standard buy-side construction. On one side, what a
company can grow at without issuing equity or adding leverage — return on equity
times the share of earnings it keeps. On the other, the growth a constant-payout
Gordon model needs in order to justify today's price at a stated cost of equity.
Where the two disagree by a wide margin, something has to give: either the
company outgrows what its book can fund (by raising capital, or by earning a
higher return than it does now), or the price comes down.

The screen has a known asymmetry and it is stated rather than smoothed over.
Priced-in growth is bounded — it cannot exceed the cost of equity — while
sustainable growth is unbounded above, so surpluses outnumber deficits by
construction. The deficit side is where the screen actually bites.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from . import config
from .derive import priced_in_growth

# Above this return on equity the Gordon identity stops describing a real
# constraint. Sustained buybacks shrink book equity towards zero, so ROE rises
# without the company's capacity to grow rising with it, and ROE x retention
# returns a growth rate in the hundreds of percent. The arithmetic is correct
# and the economics is not, so those names are reported and set aside rather
# than screened on.
ROE_INTERPRETABLE_MAX = 0.40


def build_screen(core: pd.DataFrame, cost_of_equity: float = config.COST_OF_EQUITY,
                 terminal_payout: float = config.TERMINAL_PAYOUT) -> pd.DataFrame:
    d = core.copy()
    d["priced_in_growth"] = priced_in_growth(
        d["earnings_yield"], cost_of_equity, terminal_payout
    )
    d["growth_gap"] = d["sustainable_growth"] - d["priced_in_growth"]
    d["sgr_interpretable"] = d["roe"] <= ROE_INTERPRETABLE_MAX

    # A company on 100x+ earnings has an earnings yield close to zero, so its
    # priced-in growth is pinned at the cost of equity and the "gap" is a
    # statement about the denominator rather than about the business. Those are
    # separated out as earnings-constrained rather than distribution-constrained.
    d["earnings_constrained"] = d["price_to_earnings"] > config.FLAG_HIGH_PE
    d["in_screen"] = d["sgr_interpretable"] & ~d["earnings_constrained"]
    return d


def screen_summary(screened: pd.DataFrame,
                   threshold: float = config.GROWTH_GAP_THRESHOLD) -> dict:
    s = screened[screened["in_screen"]]
    return {
        "cost_of_equity": config.COST_OF_EQUITY,
        "terminal_payout": config.TERMINAL_PAYOUT,
        "roe_interpretable_max": ROE_INTERPRETABLE_MAX,
        "gap_threshold": threshold,
        "core_universe": int(len(screened)),
        "excluded_roe_above_max": int((~screened["sgr_interpretable"]).sum()),
        "excluded_earnings_constrained": int(
            (screened["sgr_interpretable"] & screened["earnings_constrained"]).sum()
        ),
        "screen_universe": int(len(s)),
        "median_sustainable_growth": float(s["sustainable_growth"].median()),
        "median_priced_in_growth": float(s["priced_in_growth"].median()),
        "median_gap": float(s["growth_gap"].median()),
        "n_funding_surplus": int((s["growth_gap"] > threshold).sum()),
        "n_funding_deficit": int((s["growth_gap"] < -threshold).sum()),
        "n_broadly_consistent": int((s["growth_gap"].abs() <= threshold).sum()),
        "share_in_deficit": float((s["growth_gap"] < -threshold).mean()),
        "deficit_market_cap": float(
            s.loc[s["growth_gap"] < -threshold, "market_cap"].sum()
        ),
        "deficit_median_payout": float(
            s.loc[s["growth_gap"] < -threshold, "payout_ratio"].median()
        ),
        "deficit_median_roe": float(s.loc[s["growth_gap"] < -threshold, "roe"].median()),
        "surplus_median_payout": float(
            s.loc[s["growth_gap"] > threshold, "payout_ratio"].median()
        ),
        "surplus_median_roe": float(s.loc[s["growth_gap"] > threshold, "roe"].median()),
    }


COLUMNS = [
    "symbol", "name", "sector", "sub_industry", "market_cap", "price",
    "price_to_earnings", "earnings_yield", "roe", "payout_ratio",
    "retention_ratio", "sustainable_growth", "priced_in_growth", "growth_gap",
    "ebitda_margin", "net_margin", "range_position",
]


def extremes(screened: pd.DataFrame, n: int = 15) -> pd.DataFrame:
    """The names where the two growth numbers disagree most, both directions."""
    s = screened[screened["in_screen"]]
    deficit = s.nsmallest(n, "growth_gap").assign(
        side="priced above what the balance sheet can fund"
    )
    surplus = s.nlargest(n, "growth_gap").assign(
        side="can fund more than the price requires"
    )
    return pd.concat([deficit, surplus])[COLUMNS + ["side"]].reset_index(drop=True)


def sweep_cost_of_equity(core: pd.DataFrame,
                         rates=config.COST_OF_EQUITY_SWEEP,
                         threshold: float = config.GROWTH_GAP_THRESHOLD) -> pd.DataFrame:
    """Re-run the screen across the cost of equity.

    The result is worth stating up front, because it is not what a reader
    expects from a sensitivity table. Priced-in growth is r - (E/P) x b, so
    changing r shifts every company's priced-in growth by exactly the same
    constant. The *ranking* of the disagreement is therefore invariant to the
    assumption — the Spearman correlation against the base case is 1 by
    construction, and it is computed here rather than asserted. What moves is
    only how many names sit either side of the threshold, which is a statement
    about where the line is drawn, not about which companies are where.
    """
    base = build_screen(core, config.COST_OF_EQUITY)
    base_gap = base.loc[base["in_screen"], "growth_gap"]

    rows = []
    for r in rates:
        d = build_screen(core, r)
        s = d[d["in_screen"]]
        rows.append(
            {
                "cost_of_equity": r,
                "median_priced_in_growth": float(s["priced_in_growth"].median()),
                "median_gap": float(s["growth_gap"].median()),
                "n_funding_deficit": int((s["growth_gap"] < -threshold).sum()),
                "n_funding_surplus": int((s["growth_gap"] > threshold).sum()),
                "n_broadly_consistent": int((s["growth_gap"].abs() <= threshold).sum()),
                "rank_corr_vs_base": float(
                    stats.spearmanr(base_gap, s.loc[base_gap.index, "growth_gap"]).statistic
                ),
            }
        )
    return pd.DataFrame(rows)


def peer_table(core: pd.DataFrame, sector: str) -> pd.DataFrame:
    """Rank one sector's constituents on profitability, returns and price.

    Ranks are computed within the sector, not against the index, because the
    question is which of these companies is the better holding relative to its
    alternatives — not whether the sector as a whole is attractive.

    The composite is an unweighted average of three percentile ranks: EBITDA
    margin, ROE and earnings yield. Equal weights are a decision, not a result;
    weighting them would need a view about what the reader is buying, and the
    three columns are reported alongside so anyone can reweight.
    """
    s = core[core["sector"] == sector].copy()
    for col, name in (
        ("ebitda_margin", "rank_margin"),
        ("roe", "rank_roe"),
        ("earnings_yield", "rank_earnings_yield"),
    ):
        s[name] = s[col].rank(pct=True)

    s["composite_rank"] = s[["rank_margin", "rank_roe", "rank_earnings_yield"]].mean(axis=1)

    # A name in the cheap half on price and the bottom half on both quality
    # measures is not a bargain, it is priced where it is for a reason. Naming
    # that split is the whole point of a peer table.
    s["classification"] = np.select(
        [
            (s["rank_margin"] >= 0.5) & (s["rank_roe"] >= 0.5) & (s["rank_earnings_yield"] >= 0.5),
            (s["rank_margin"] >= 0.5) & (s["rank_roe"] >= 0.5),
            (s["rank_earnings_yield"] >= 0.5),
        ],
        ["quality at a discount", "quality, fully priced", "cheap on price alone"],
        default="expensive without the quality",
    )

    cols = [
        "symbol", "name", "sub_industry", "market_cap", "ebitda_margin", "net_margin",
        "roe", "price_to_earnings", "earnings_yield", "sustainable_growth",
        "rank_margin", "rank_roe", "rank_earnings_yield", "composite_rank",
        "classification",
    ]
    return s.sort_values("composite_rank", ascending=False)[cols].reset_index(drop=True)


def largest_sector_by_market_cap(base: pd.DataFrame) -> tuple[str, dict]:
    caps = base.groupby("sector")["market_cap"].sum().sort_values(ascending=False)
    name = str(caps.index[0])
    return name, {
        "sector": name,
        "market_cap": float(caps.iloc[0]),
        "share_of_index_market_cap": float(caps.iloc[0] / caps.sum()),
        "constituents_in_base": int((base["sector"] == name).sum()),
    }
