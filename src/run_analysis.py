"""End-to-end run. Every number quoted in the report pack is produced here.

    python -m src.run_analysis
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd

from . import config, dispersion, figures, screen, valuation
from .ingest import build
from .sectors import SUBINDUSTRY_TO_SECTOR

EXTRACT_COLUMNS = [
    "symbol", "name", "sector", "sub_industry", "price", "market_cap",
    "price_to_earnings", "price_to_sales", "price_to_book", "dividend_yield",
    "eps", "ebitda", "revenue", "book_equity", "net_income", "shares_outstanding",
    "ebitda_margin", "net_margin", "roe", "payout_ratio", "retention_ratio",
    "earnings_yield", "sustainable_growth", "range_position",
    "in_base", "in_margin", "in_returns", "in_core", "fail_reasons",
]


def main() -> dict:
    for path in (config.PROCESSED, config.FIGURES, config.TABLES, config.EXTRACTS):
        path.mkdir(parents=True, exist_ok=True)

    tagged, quality = build()
    tagged.to_parquet(config.PROCESSED / "constituents.parquet", index=False)

    base = tagged[tagged["in_base"]].copy()
    margin_universe = tagged[tagged["in_margin"]].copy()
    core = tagged[tagged["in_core"]].copy()

    # The sub-industry mapping is exported so sql/01_staging.sql loads exactly
    # the mapping the Python path uses, rather than a second copy that can drift.
    pd.DataFrame(
        sorted(SUBINDUSTRY_TO_SECTOR.items()), columns=["sub_industry", "sector"]
    ).to_csv(config.TABLES / "gics_sector_mapping.csv", index=False)

    excluded = tagged[~tagged["in_core"]][
        ["symbol", "name", "sector", "sub_industry", "market_cap", "fail_reasons",
         "in_base", "in_margin", "in_returns"]
    ].sort_values("market_cap", ascending=False)
    excluded.to_csv(config.TABLES / "excluded_constituents.csv", index=False)

    # --- Index position ------------------------------------------------------
    position = {
        "constituents_in_file": int(quality["rows_in"]),
        "distinct_companies": int(len(base)),
        "index_market_cap": float(base["market_cap"].sum()),
        "aggregate_revenue_core": float(core["revenue"].sum()),
        "aggregate_ebitda_core": float(core["ebitda"].sum()),
        "aggregate_net_income_core": float(core["net_income"].sum()),
        "aggregate_ebitda_margin_core": float(
            core["ebitda"].sum() / core["revenue"].sum()
        ),
        "aggregate_net_margin_core": float(
            core["net_income"].sum() / core["revenue"].sum()
        ),
        "median_ebitda_margin_margin_universe": float(
            margin_universe["ebitda_margin"].median()
        ),
        "median_net_margin_core": float(core["net_margin"].median()),
        "median_roe_core": float(core["roe"].median()),
        "median_pe_core": float(core["price_to_earnings"].median()),
        "median_payout_core": float(core["payout_ratio"].median()),
        "cap_weighted_pe_core": float(
            core["market_cap"].sum() / core["net_income"].sum()
        ),
        "loss_making_constituents": int(quality["rows_failing_each_rule"]["negative_trailing_eps"]),
        "negative_book_constituents": int(quality["rows_failing_each_rule"]["non_positive_book"]),
        "payout_above_earnings_constituents": int(
            quality["rows_failing_each_rule"]["payout_above_earnings"]
        ),
    }

    # --- 1. Sector profitability dispersion ----------------------------------
    disp = dispersion.run(margin_universe, core)
    for name, table in disp["tables"].items():
        table.to_csv(config.TABLES / f"{name}.csv", index=False)

    # --- 2. Quality versus price ---------------------------------------------
    val = valuation.run(core)
    for name, table in val["tables"].items():
        table.to_csv(config.TABLES / f"{name}.csv", index=False)

    # --- 3. Implied growth screen --------------------------------------------
    screened = screen.build_screen(core)
    screen_metrics = screen.screen_summary(screened)
    gap_extremes = screen.extremes(screened)
    sweep = screen.sweep_cost_of_equity(core)
    gap_extremes.to_csv(config.TABLES / "growth_gap_extremes.csv", index=False)
    sweep.to_csv(config.TABLES / "cost_of_equity_sensitivity.csv", index=False)

    # Sector composition of the deficit list. The mechanism matters more than
    # the names: if the deficits cluster in high-payout sectors, the screen is
    # picking up distribution policy rather than mispricing.
    deficit = screened[
        screened["in_screen"]
        & (screened["growth_gap"] < -config.GROWTH_GAP_THRESHOLD)
    ]
    screen_metrics["deficit_by_sector"] = (
        deficit["sector"].value_counts().to_dict()
    )
    screen_metrics["deficit_top_10"] = (
        deficit.nsmallest(10, "growth_gap")[
            ["symbol", "name", "sector", "roe", "payout_ratio",
             "sustainable_growth", "priced_in_growth", "growth_gap",
             "price_to_earnings", "dividend_yield"]
        ].to_dict("records")
    )
    surplus = screened[
        screened["in_screen"]
        & (screened["growth_gap"] > config.GROWTH_GAP_THRESHOLD)
    ]
    screen_metrics["surplus_top_10"] = (
        surplus.nlargest(10, "growth_gap")[
            ["symbol", "name", "sector", "roe", "payout_ratio",
             "sustainable_growth", "priced_in_growth", "growth_gap",
             "price_to_earnings"]
        ].to_dict("records")
    )

    # --- 4. Peer benchmarking, largest sector --------------------------------
    sector_name, sector_position = screen.largest_sector_by_market_cap(base)
    peers = screen.peer_table(core, sector_name)
    peers.to_csv(config.TABLES / "peer_benchmark_largest_sector.csv", index=False)

    peer_metrics = {
        **sector_position,
        "constituents_in_core": int(len(peers)),
        "classification_counts": peers["classification"].value_counts().to_dict(),
        "quality_at_a_discount": peers[
            peers["classification"] == "quality at a discount"
        ][["symbol", "name", "ebitda_margin", "roe", "price_to_earnings",
           "composite_rank"]].to_dict("records"),
        "cheap_on_price_alone": peers[
            peers["classification"] == "cheap on price alone"
        ].nlargest(8, "earnings_yield")[
            ["symbol", "name", "ebitda_margin", "roe", "price_to_earnings",
             "earnings_yield"]
        ].to_dict("records"),
        "median_ebitda_margin": float(peers["ebitda_margin"].median()),
        "median_roe": float(peers["roe"].median()),
        "median_pe": float(peers["price_to_earnings"].median()),
    }

    # --- Dashboard extracts ---------------------------------------------------
    fct = screened[[c for c in EXTRACT_COLUMNS if c in screened.columns]
                   + ["priced_in_growth", "growth_gap", "in_screen"]]
    fct.to_csv(config.EXTRACTS / "fct_constituent_fundamentals.csv", index=False)
    disp["tables"]["ebitda_margin_by_sector"].to_csv(
        config.EXTRACTS / "agg_sector_margins.csv", index=False
    )
    peers.to_csv(config.EXTRACTS / "dim_peer_benchmark.csv", index=False)
    sweep.to_csv(config.EXTRACTS / "agg_cost_of_equity_sweep.csv", index=False)

    # --- Figures --------------------------------------------------------------
    figures.margin_dispersion(
        disp["tables"]["ebitda_margin_by_sector"],
        disp["metrics"]["ebitda_margin_by_sector"],
        disp["metrics"]["spread"],
        config.FIGURES / "01-margin-dispersion-by-sector.png",
    )
    figures.quality_versus_price(
        core, val["metrics"]["primary"],
        config.FIGURES / "02-quality-versus-price.png",
    )
    figures.book_multiple_decomposition(
        val["metrics"]["book_multiple_decomposition"],
        config.FIGURES / "03-book-multiple-decomposition.png",
    )
    figures.growth_gap(
        screened, screen_metrics, config.FIGURES / "04-implied-growth-gap.png"
    )
    figures.peer_benchmark(
        peers, sector_name, config.FIGURES / "05-peer-benchmark.png"
    )
    figures.cost_of_equity_sensitivity(
        sweep, config.FIGURES / "06-cost-of-equity-sensitivity.png"
    )

    metrics = {
        "data_quality": quality,
        "position": position,
        "dispersion": disp["metrics"],
        "valuation": val["metrics"],
        "growth_screen": screen_metrics,
        "cost_of_equity_sweep": sweep.to_dict("records"),
        "peer_benchmark": peer_metrics,
        "assumptions": {
            "cost_of_equity": config.COST_OF_EQUITY,
            "cost_of_equity_sweep": list(config.COST_OF_EQUITY_SWEEP),
            "terminal_payout": config.TERMINAL_PAYOUT,
            "growth_gap_threshold": config.GROWTH_GAP_THRESHOLD,
            "roe_interpretable_max": screen.ROE_INTERPRETABLE_MAX,
            "winsorisation": [config.WINSOR_LOWER, config.WINSOR_UPPER],
            "screen_bounds": {
                "min_pe": config.MIN_PE,
                "min_pb": config.MIN_PB,
                "max_pb": config.MAX_PB,
                "max_payout_ratio": config.MAX_PAYOUT_RATIO,
                "ebitda_margin_bounds": [config.MIN_EBITDA_MARGIN, config.MAX_EBITDA_MARGIN],
                "flag_high_pe": config.FLAG_HIGH_PE,
                "flag_high_ps": config.FLAG_HIGH_PS,
            },
        },
    }

    def default(obj):
        if isinstance(obj, (np.integer,)):
            return int(obj)
        if isinstance(obj, (np.floating,)):
            return None if np.isnan(obj) else float(obj)
        if isinstance(obj, (np.bool_,)):
            return bool(obj)
        if isinstance(obj, pd.Timestamp):
            return obj.isoformat()
        return float(obj)

    with open(config.OUTPUTS / "metrics.json", "w") as fh:
        json.dump(metrics, fh, indent=2, default=default)

    print(
        f"universes  base={quality['universe_sizes']['base']}  "
        f"margin={quality['universe_sizes']['margin']}  "
        f"core={quality['universe_sizes']['core']}"
    )
    print(
        "sector eta^2 (EBITDA margin) = "
        f"{disp['metrics']['ebitda_margin_by_sector']['eta_squared']:.3f}; "
        "operating companies only = "
        f"{disp['metrics']['ebitda_margin_by_sector_operating_only']['eta_squared']:.3f}"
    )
    print(
        "log P/B variance from ROE = "
        f"{val['metrics']['book_multiple_decomposition']['share_from_roe']:.3f}"
    )
    return metrics


if __name__ == "__main__":
    main()
