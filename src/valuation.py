"""Does the market pay a higher multiple for a better business?

Two things have to be settled before this question can be asked of this extract.

**One: most "quality" measures here are algebraically entangled with the
multiples.** Working from the identities in `derive.py`:

    ROE        = (P/B) / (P/E)
    net margin = EPS x (P/S) / P = (E/P) x (P/S)

Both are functions of the valuation ratios. Regressing a multiple on either is
regressing a variable on a rearrangement of itself, and any R-squared that comes
out is not evidence about investor behaviour. The EBITDA margin is the exception:
EBITDA arrives as an absolute currency figure and revenue is M/(P/S), so the
price terms cancel and what is left is a pure fundamental. It is the only
quality measure in this dataset that carries information the multiples do not
already contain, and it is therefore the regressor in the primary specification.

**Two: the price-to-book multiple decomposes exactly.** Taking logs of the ROE
identity and rearranging:

    log(P/B) = log(ROE) + log(P/E)

so

    var[log(P/B)] = var[log(ROE)] + var[log(P/E)] + 2 cov[log(ROE), log(P/E)]

This is arithmetic, not a model, and it settles the question more cleanly than
any regression: it says exactly how much of the dispersion in what investors pay
per dollar of book is dispersion in the returns those books earn, and how much
is dispersion in valuation proper. `book_multiple_decomposition` computes it.

The naive specification everyone runs first — earnings yield on ROE and margin —
is fitted too, and reported, because the interesting thing about it is what it
does not find.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import statsmodels.api as sm

from . import config


def winsorise(s: pd.Series, lower: float = config.WINSOR_LOWER,
              upper: float = config.WINSOR_UPPER) -> pd.Series:
    """Two-sided clip at the stated percentiles.

    Applied to regression inputs only. A P/E of 5,085 is a real observation
    about a company with almost no trailing earnings, and it belongs in the
    reported distribution; what it does not belong in is an unweighted least
    squares fit, where it would set the slope on its own.
    """
    return s.clip(s.quantile(lower), s.quantile(upper))


def _prepare(df: pd.DataFrame) -> pd.DataFrame:
    d = df.copy()
    d["log_pe"] = np.log(d["price_to_earnings"])
    d["log_pb"] = np.log(d["price_to_book"])
    d["log_roe"] = np.log(d["roe"])
    d["log_market_cap"] = np.log(d["market_cap"])
    for col in ("log_pe", "log_pb", "log_market_cap", "ebitda_margin", "net_margin",
                "roe", "earnings_yield", "sustainable_growth"):
        d[f"w_{col}"] = winsorise(d[col])
    return d


def _fit(d: pd.DataFrame, y: str, xs: list[str], label: str,
         sector_fe: bool = False) -> dict:
    cols = [y] + xs + (["sector"] if sector_fe else [])
    sample = d[cols].dropna()
    design = sample[xs].astype(float)
    if sector_fe:
        design = pd.concat(
            [design, pd.get_dummies(sample["sector"], drop_first=True).astype(float)],
            axis=1,
        )
    model = sm.OLS(sample[y], sm.add_constant(design)).fit()
    return {
        "specification": label,
        "dependent": y,
        "n": int(model.nobs),
        "r_squared": float(model.rsquared),
        "adj_r_squared": float(model.rsquared_adj),
        "sector_fixed_effects": bool(sector_fe),
        "terms": [
            {
                "term": term,
                "coefficient": float(model.params[term]),
                "std_error": float(model.bse[term]),
                "t_stat": float(model.tvalues[term]),
                "p_value": float(model.pvalues[term]),
            }
            for term in ["const"] + xs
        ],
        "_model": model,
        "_sample": sample,
    }


def book_multiple_decomposition(df: pd.DataFrame) -> dict:
    """Split the variance of log(P/B) into a return component and a price one.

    Exact by the identity log(P/B) = log(ROE) + log(P/E). The residual check is
    kept in the output so a reader can see the decomposition is arithmetic
    rather than an approximation.
    """
    d = df[["price_to_book", "price_to_earnings", "roe"]].dropna()
    log_pb = np.log(d["price_to_book"])
    log_pe = np.log(d["price_to_earnings"])
    log_roe = np.log(d["roe"])

    var_pb = float(log_pb.var())
    var_roe = float(log_roe.var())
    var_pe = float(log_pe.var())
    cov = float(log_roe.cov(log_pe))

    return {
        "n": int(len(d)),
        "identity_max_abs_residual": float((log_pb - log_roe - log_pe).abs().max()),
        "var_log_price_to_book": var_pb,
        "var_log_roe": var_roe,
        "var_log_price_to_earnings": var_pe,
        "covariance_term": 2 * cov,
        "share_from_roe": var_roe / var_pb,
        "share_from_earnings_multiple": var_pe / var_pb,
        "share_from_covariance": 2 * cov / var_pb,
        "corr_log_roe_log_pe": float(log_roe.corr(log_pe)),
    }


def residual_table(fit: dict, df: pd.DataFrame, n: int = 10) -> pd.DataFrame:
    """The names the primary specification misses by the most, both ways.

    A residual here is the gap between the multiple a company trades on and the
    multiple its margin and size would predict. It is a starting point for
    questions, not a signal: the model explains a small share of the variation,
    so most of the residual is things the model does not contain.
    """
    model, sample = fit["_model"], fit["_sample"]
    resid = pd.Series(model.resid, index=sample.index, name="residual_log_pe")
    joined = df.loc[resid.index, [
        "symbol", "name", "sector", "market_cap", "ebitda_margin", "roe",
        "price_to_earnings",
    ]].join(resid)
    joined["implied_multiple_gap"] = np.exp(joined["residual_log_pe"]) - 1
    top = joined.nlargest(n, "residual_log_pe").assign(direction="richer than fundamentals")
    bottom = joined.nsmallest(n, "residual_log_pe").assign(direction="cheaper than fundamentals")
    return pd.concat([top, bottom]).reset_index(drop=True)


def run(core: pd.DataFrame) -> dict:
    """Fit the specifications and return metrics plus the residual table."""
    d = _prepare(core)

    naive = _fit(d, "w_earnings_yield", ["w_roe", "w_net_margin"],
                 "earnings yield ~ ROE + net margin (entangled)")
    pe_margin = _fit(d, "w_log_pe", ["w_ebitda_margin"],
                     "log P/E ~ EBITDA margin")
    primary = _fit(d, "w_log_pe", ["w_ebitda_margin", "w_log_market_cap"],
                   "log P/E ~ EBITDA margin + log size")
    with_growth = _fit(d, "w_log_pe",
                       ["w_ebitda_margin", "w_log_market_cap", "w_sustainable_growth"],
                       "log P/E ~ EBITDA margin + log size + sustainable growth")
    with_fe = _fit(d, "w_log_pe", ["w_ebitda_margin", "w_log_market_cap"],
                   "log P/E ~ EBITDA margin + log size + sector fixed effects",
                   sector_fe=True)
    pb_roe = _fit(d, "w_log_pb", ["w_roe", "w_log_market_cap"],
                  "log P/B ~ ROE + log size (mechanically linked, see decomposition)")

    fits = [naive, pe_margin, primary, with_growth, with_fe, pb_roe]
    summary = pd.DataFrame(
        [
            {
                "specification": f["specification"],
                "n": f["n"],
                "r_squared": round(f["r_squared"], 4),
                "adj_r_squared": round(f["adj_r_squared"], 4),
            }
            for f in fits
        ]
    )
    coefficients = pd.DataFrame(
        [{"specification": f["specification"], **t} for f in fits for t in f["terms"]]
    )

    return {
        "tables": {
            "regression_summary": summary,
            "regression_coefficients": coefficients,
            "valuation_residuals": residual_table(primary, core),
        },
        "metrics": {
            "specifications": [
                {k: v for k, v in f.items() if not k.startswith("_")} for f in fits
            ],
            "primary": {k: v for k, v in primary.items() if not k.startswith("_")},
            "book_multiple_decomposition": book_multiple_decomposition(core),
        },
    }
