"""Load the constituent extract, normalise it, and gate it on an explicit screen.

Nothing is dropped quietly. Every row removed is counted, attributed to the rule
that removed it, and written to `outputs/metrics.json` under `data_quality`. The
excluded rows are also written out in full to
`outputs/tables/excluded_constituents.csv` so the exclusions can be argued with.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import config
from .derive import add_fundamentals
from .sectors import map_sector

COLUMN_MAP = {
    "Symbol": "symbol",
    "Name": "name",
    "Sector": "sub_industry",       # mislabelled at source; it is GICS sub-industry
    "Price": "price",
    "Price/Earnings": "price_to_earnings",
    "Dividend Yield": "dividend_yield",
    "Earnings/Share": "eps",
    "52 Week Low": "week52_low",
    "52 Week High": "week52_high",
    "Market Cap": "market_cap",
    "EBITDA": "ebitda",
    "Price/Sales": "price_to_sales",
    "Price/Book": "price_to_book",
    "SEC Filings": "sec_filings_url",
}

# Companies with two listed share classes appear twice with the same underlying
# accounts. Left in, the market-cap-weighted aggregates double-count them and the
# regression treats one company as two observations. The junior class is flagged
# rather than deleted, so the count of affected rows stays visible.
DUAL_CLASS_SECONDARY = ("GOOG", "FOX", "NWS")

REQUIRED_FOR_ANALYSIS = [
    "price", "market_cap", "price_to_earnings", "price_to_sales",
    "price_to_book", "eps",
]


def load_raw() -> pd.DataFrame:
    if not config.SOURCE_FILE.exists():
        raise FileNotFoundError(
            f"{config.SOURCE_FILE} not found. Run `make data` to fetch it from "
            f"{config.SOURCE_URL}"
        )
    return pd.read_csv(config.SOURCE_FILE)


def normalise(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Rename, type, map sectors and record what arrived."""
    log: dict = {"rows_in": int(len(df))}

    out = df.rename(columns=COLUMN_MAP).copy()
    out["symbol"] = out["symbol"].str.strip()
    out["sub_industry"] = out["sub_industry"].str.strip()

    # Fails loudly on an unmapped sub-industry rather than bucketing it to
    # "Other", where it would quietly distort the between-sector comparison.
    out["sector"] = out["sub_industry"].map(map_sector)

    out["is_dual_class_secondary"] = out["symbol"].isin(DUAL_CLASS_SECONDARY)

    # A missing dividend yield in this source means the vendor recorded no
    # dividend, not that the value is unknown; every payer has the field
    # populated. Filling with zero is therefore a statement about the world, and
    # the count is logged so the reader can disagree with it.
    log["dividend_yield_missing_filled_zero"] = int(out["dividend_yield"].isna().sum())
    out["dividend_yield"] = out["dividend_yield"].fillna(0.0)

    log["sub_industries"] = int(out["sub_industry"].nunique())
    log["sectors"] = int(out["sector"].nunique())
    log["dual_class_secondary_rows"] = int(out["is_dual_class_secondary"].sum())

    # Rows with no market data at all. These are not random: the constituent
    # roster and the price vector were assembled at different times, so names
    # that have left the index through acquisition or take-private survive in the
    # list with every numeric field null. Two more are dot-suffixed share-class
    # tickers (BRK.B, BF.B) that commonly fail a vendor symbol lookup.
    numeric = [c for c in REQUIRED_FOR_ANALYSIS if c in out.columns]
    all_null = out[numeric].isna().all(axis=1)
    log["rows_with_no_market_data"] = int(all_null.sum())
    log["symbols_with_no_market_data"] = sorted(out.loc[all_null, "symbol"].tolist())

    log["missing_by_field"] = {
        c: int(out[c].isna().sum()) for c in COLUMN_MAP.values() if c in out.columns
        and out[c].dtype.kind in "fc"
    }
    return out, log


def integrity_screen(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Tag every row with the rules it trips and the universes it qualifies for.

    Nothing is deleted here. The function returns the whole frame with boolean
    columns attached, and each analysis then states which universe it runs on.
    That is deliberate: a company with negative book equity is unusable for ROE
    and perfectly usable for an EBITDA margin, and collapsing both decisions into
    one "clean" table loses observations for no reason.

    Three nested universes come out of it:

    - `in_base`      — a real, distinct company with market data. Everything else
                       is measured against this denominator.
    - `in_margin`    — base, plus a derivable revenue and a possible EBITDA
                       margin. Used for the profitability dispersion work.
    - `in_returns`   — base, plus a defined ROE and a defined payout. Used for
                       anything touching return on equity or implied growth.
    - `in_core`      — margin and returns together. Used for the regression, the
                       growth screen and the peer table.

    The rules only remove observations where the arithmetic is undefined or
    impossible. Expensive is not the same as wrong, so a high multiple is
    flagged and winsorised in the regression rather than screened out.
    """
    d = df.copy()
    fails: dict[str, pd.Series] = {}

    # --- Identity / duplication ---------------------------------------------
    fails["no_market_data"] = d[REQUIRED_FOR_ANALYSIS].isna().all(axis=1)
    fails["dual_class_secondary"] = d["is_dual_class_secondary"]

    # --- Revenue and margin --------------------------------------------------
    fails["revenue_not_derivable"] = d["revenue"].isna() | (d["revenue"] <= 0)
    fails["ebitda_missing"] = d["ebitda"].isna()
    fails["ebitda_margin_impossible"] = (
        (d["ebitda_margin"] > config.MAX_EBITDA_MARGIN)
        | (d["ebitda_margin"] < config.MIN_EBITDA_MARGIN)
    ).fillna(False)

    # --- Returns and payout --------------------------------------------------
    # The source records no negative P/E at all: where trailing EPS is negative
    # it nulls the multiple instead. So "P/E missing" is not missingness, it is
    # a loss-making company, and the two are separated here so the count of
    # loss-makers is reported rather than buried in a null count.
    fails["negative_trailing_eps"] = (d["eps"] <= 0).fillna(False)
    fails["pe_missing"] = d["price_to_earnings"].isna() & ~fails["negative_trailing_eps"]
    fails["non_positive_pe"] = (d["price_to_earnings"] <= config.MIN_PE).fillna(False)
    fails["non_positive_book"] = (d["price_to_book"] <= config.MIN_PB).fillna(False)
    fails["pb_missing"] = d["price_to_book"].isna()
    fails["book_near_zero"] = (d["price_to_book"] > config.MAX_PB).fillna(False)
    fails["payout_above_earnings"] = (
        d["payout_ratio"] > config.MAX_PAYOUT_RATIO
    ).fillna(False)

    flags = pd.DataFrame(fails).fillna(False)
    d = d.join(flags.add_prefix("fail_"))

    base = ~flags["no_market_data"] & ~flags["dual_class_secondary"]
    margin_ok = ~(
        flags["revenue_not_derivable"]
        | flags["ebitda_missing"]
        | flags["ebitda_margin_impossible"]
    )
    returns_ok = ~(
        flags["negative_trailing_eps"] | flags["pe_missing"] | flags["non_positive_pe"]
        | flags["non_positive_book"] | flags["pb_missing"] | flags["book_near_zero"]
        | flags["payout_above_earnings"]
    )

    d["in_base"] = base
    d["in_margin"] = base & margin_ok
    d["in_returns"] = base & returns_ok
    d["in_core"] = base & margin_ok & returns_ok
    d["fail_reasons"] = flags.apply(
        lambda r: "; ".join(sorted(flags.columns[r.to_numpy()])), axis=1
    )

    # Retained but noteworthy. Reported, winsorised in the regression, never cut.
    d["flag_high_pe"] = (d["price_to_earnings"] > config.FLAG_HIGH_PE).fillna(False)
    d["flag_high_ps"] = (d["price_to_sales"] > config.FLAG_HIGH_PS).fillna(False)

    # Market-cap shares are taken against the base universe, not the raw file.
    # The file total double-counts the three dual-class companies, which would
    # understate every universe's coverage by about six points.
    total_cap = float(d["market_cap"].sum(skipna=True))
    base_cap = float(d.loc[base, "market_cap"].sum(skipna=True))
    log = {
        "rows_screened": int(len(d)),
        # Rule counts overlap by design: a row can trip several at once, so
        # these sum to more than the number of rows removed from any universe.
        "rows_failing_each_rule": {c: int(flags[c].sum()) for c in flags.columns},
        "universe_sizes": {
            "base": int(base.sum()),
            "margin": int(d["in_margin"].sum()),
            "returns": int(d["in_returns"].sum()),
            "core": int(d["in_core"].sum()),
        },
        "excluded_from_base": int((~base).sum()),
        "excluded_from_core": int(base.sum() - d["in_core"].sum()),
        "core_exclusion_rate_within_base": round(
            float(1 - d["in_core"].sum() / base.sum()), 6
        ),
        "market_cap_in_file": total_cap,
        "market_cap_base": base_cap,
        "share_of_base_market_cap": {
            u: round(float(d.loc[d[f"in_{u}"], "market_cap"].sum(skipna=True) / base_cap), 6)
            for u in ("margin", "returns", "core")
        },
        "flagged_high_pe": int(d["flag_high_pe"].sum()),
        "flagged_high_ps": int(d["flag_high_ps"].sum()),
    }
    return d, log


def build() -> tuple[pd.DataFrame, dict]:
    """Full ingest: load, normalise, derive, screen. Returns (tagged frame, log)."""
    raw = load_raw()
    normalised, log = normalise(raw)
    with_fundamentals = add_fundamentals(normalised)
    tagged, screen_log = integrity_screen(with_fundamentals)

    # Cross-check on the two routes to net income. In this source it returns
    # zero, which does not validate anything: the vendor computes P/E as
    # price ÷ EPS, so M/(P/E) and EPS x (M/P) are the same expression rearranged.
    # The check is kept as a tripwire — if the source ever starts sourcing P/E
    # independently, a real gap will appear here rather than silently propagate.
    core = tagged[tagged["in_core"]]
    err = core["ni_reconciliation_error"].replace([np.inf, -np.inf], np.nan)
    screen_log["net_income_reconciliation"] = {
        "median_relative_gap": float(err.median()),
        "max_relative_gap": float(err.max()),
        "rows_over_1pct_gap": int((err > 0.01).sum()),
        "note": "tautological in this source: P/E is computed as price / EPS",
    }

    log.update(screen_log)
    return tagged, log
