"""Reconstruct the fundamentals from the ratio set.

The extract carries no income statement and no balance sheet — only price, market
capitalisation, EBITDA and four valuation multiples. Everything the analysis
needs is recoverable from those by algebra, because a multiple is a ratio of two
things and market capitalisation supplies the numerator.

Each derivation is stated as its identity before it is coded. The algebra is the
point: none of these are estimates or proxies, they are the same quantity written
a different way, and they are exact wherever the vendor computed the multiple
from the same period's accounts as the market cap. Where the vendor mixed periods
— a trailing multiple against a current price — the error lands in the derived
figure, which is what the integrity screen in `ingest.py` is for.

Identities used, with S = shares outstanding, P = price, M = market cap:

    S       = M / P
    Revenue = M / (P/S)                     since P/S = M / Revenue
    Net income
            = EPS x S                       since EPS = E / S
    Book value
            = M / (P/B)                     since P/B = M / Book
    ROE     = (P/B) / (P/E)                 see roe() below
    Payout  = (D/P) x (P/E)                 see payout_ratio() below
    g_sust  = ROE x (1 - payout)            Gordon sustainable growth
    E/P     = 1 / (P/E)                     earnings yield
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def shares_outstanding(market_cap: pd.Series, price: pd.Series) -> pd.Series:
    """S = M / P.

    Exact by definition of market capitalisation. The only way this goes wrong
    is a price and a share count struck on different dates, which shows up as a
    share count that disagrees with the EPS-implied one — checked in
    `reconciliation_error`.
    """
    return market_cap / price.replace(0, np.nan)


def revenue(market_cap: pd.Series, price_to_sales: pd.Series) -> pd.Series:
    """Revenue = M / (P/S).

    P/S is quoted per share (price / sales-per-share), but the per-share terms
    cancel: P/S = (M/S) / (Rev/S) = M / Rev. So dividing market cap by it
    returns total revenue, not revenue per share.
    """
    return market_cap / price_to_sales.replace(0, np.nan)


def book_value(market_cap: pd.Series, price_to_book: pd.Series) -> pd.Series:
    """Book equity = M / (P/B). Same per-share cancellation as revenue."""
    return market_cap / price_to_book.replace(0, np.nan)


def net_income(eps: pd.Series, shares: pd.Series) -> pd.Series:
    """Net income = EPS x S.

    Trailing EPS against a current share count, so this is the weaker of the two
    routes to earnings. The other route — M / (P/E) — is used as a cross-check
    in `reconciliation_error` rather than being averaged in; averaging two
    inconsistent estimates hides the inconsistency.
    """
    return eps * shares


def roe(price_to_book: pd.Series, price_to_earnings: pd.Series) -> pd.Series:
    """ROE = (P/B) / (P/E).

    The identity, written out:

        P/B ÷ P/E = (P/B) x (E/P) = E/B = return on book equity

    Price cancels completely, which is why this is a *fundamental* ratio derived
    from two *market* ratios and carries no valuation content of its own. That
    property is what makes the quality-versus-price regression in `valuation.py`
    legitimate: the left-hand side (earnings yield) and the right-hand side (ROE)
    share the price term algebraically, so the regression is run on the
    orthogonalised form described there.

    Undefined for negative book or negative earnings; those rows are removed by
    the integrity screen, not silently signed.
    """
    return price_to_book / price_to_earnings.replace(0, np.nan)


def payout_ratio(dividend_yield: pd.Series, price_to_earnings: pd.Series) -> pd.Series:
    """Payout ratio = (D/P) x (P/E).

    Written out:

        (D/P) x (P/E) = D/E = dividends ÷ earnings

    Price cancels again. A missing dividend yield in this source means "no
    dividend recorded", not "unknown": the vendor populates the field for every
    payer. It is therefore filled with zero rather than dropped, and the count of
    fills is logged so the reader can judge that call.
    """
    return dividend_yield * price_to_earnings


def earnings_yield(price_to_earnings: pd.Series) -> pd.Series:
    """E/P = 1 / (P/E). The reciprocal is the return the price implies."""
    return 1.0 / price_to_earnings.replace(0, np.nan)


def sustainable_growth(roe_: pd.Series, payout: pd.Series) -> pd.Series:
    """g = ROE x (1 - payout), the Gordon sustainable growth rate.

    The reasoning: equity grows only by earnings retained, so the maximum growth
    a company can fund without issuing equity or raising leverage is the return
    it earns on book times the fraction of earnings it keeps. This is an upper
    bound on organic growth, not a forecast.
    """
    return roe_ * (1.0 - payout)


def priced_in_growth(earnings_yield_: pd.Series, cost_of_equity: float,
                     payout: float) -> pd.Series:
    """Invert Gordon to recover the growth the price requires.

    Gordon with a constant payout ratio b on earnings E:

        P = (E x b) / (r - g)   =>   g = r - (E/P) x b

    So the growth priced in falls as the earnings yield rises. The payout term
    matters: setting b = 1 (the shortcut g = r - E/P) assumes every dollar of
    earnings is distributed, which would make a retaining company look as though
    the market demanded impossible growth from it. A single long-run market
    payout is used rather than each company's own, because the question being
    asked is what the *market* is pricing under a common terminal assumption —
    using each firm's current payout would fold company policy into a number
    meant to isolate price.
    """
    return cost_of_equity - earnings_yield_ * payout


def reconciliation_error(market_cap: pd.Series, price_to_earnings: pd.Series,
                         net_income_: pd.Series) -> pd.Series:
    """Relative gap between the two independent routes to net income.

    Route A: EPS x shares (uses the income statement and the share count).
    Route B: M / (P/E)   (uses market cap and the multiple).

    They must agree if the vendor struck every field on the same date from the
    same accounts. The gap is a direct read on how internally consistent the
    extract is, and it is reported rather than reconciled away.
    """
    route_b = market_cap / price_to_earnings.replace(0, np.nan)
    return (net_income_ - route_b).abs() / route_b.abs()


def add_fundamentals(df: pd.DataFrame) -> pd.DataFrame:
    """Attach every derived fundamental. Pure function of the ratio columns."""
    out = df.copy()

    out["shares_outstanding"] = shares_outstanding(out["market_cap"], out["price"])
    out["revenue"] = revenue(out["market_cap"], out["price_to_sales"])
    out["book_equity"] = book_value(out["market_cap"], out["price_to_book"])
    out["net_income"] = net_income(out["eps"], out["shares_outstanding"])

    out["ebitda_margin"] = out["ebitda"] / out["revenue"]
    out["net_margin"] = out["net_income"] / out["revenue"]
    out["roe"] = roe(out["price_to_book"], out["price_to_earnings"])
    out["payout_ratio"] = payout_ratio(out["dividend_yield"], out["price_to_earnings"])
    out["retention_ratio"] = 1.0 - out["payout_ratio"]
    out["earnings_yield"] = earnings_yield(out["price_to_earnings"])
    out["sustainable_growth"] = sustainable_growth(out["roe"], out["payout_ratio"])
    out["ni_reconciliation_error"] = reconciliation_error(
        out["market_cap"], out["price_to_earnings"], out["net_income"]
    )

    # Asset turnover completes the DuPont decomposition: ROE = margin x turnover
    # x leverage. Turnover and leverage are both recoverable here; the third
    # term is net margin, already computed above.
    out["asset_turnover_proxy"] = out["revenue"] / out["book_equity"]
    out["equity_multiplier_implied"] = out["roe"] / (
        out["net_margin"] * out["asset_turnover_proxy"]
    ).replace(0, np.nan)

    # Where the price sits in its own annual range. Not a fundamental, but it is
    # the cheapest available read on whether a "cheap" name is cheap because the
    # market has been marking it down.
    span = out["week52_high"] - out["week52_low"]
    out["range_position"] = (out["price"] - out["week52_low"]) / span.replace(0, np.nan)

    return out
