"""Figures for the report pack.

Every title states the finding rather than naming the variables, because a
reader who only looks at the charts should still come away with the argument.
"""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from . import config
from .sectors import NON_OPERATING_MARGIN_SECTORS
from .viz import (AXIS, INK, INK_MUTED, INK_SECONDARY, SEQUENTIAL, SERIES,
                  apply_house_style, save)

SOURCE = "Source: S&P 500 constituent financials, point-in-time snapshot (undated at source)."


def _source_line(fig, text: str, y: float = -0.03) -> None:
    fig.text(0.005, y, text, fontsize=7.5, color=INK_MUTED)


def _label_points(ax, x, y, labels, dx=5, dy=3, fontsize=7.5, color=INK_SECONDARY):
    for xi, yi, li in zip(x, y, labels):
        ax.annotate(li, (xi, yi), xytext=(dx, dy), textcoords="offset points",
                    fontsize=fontsize, color=color)


def margin_dispersion(summary: pd.DataFrame, decomp: dict, spread: dict, path) -> None:
    """Dot-with-range by sector, ordered by median.

    A box plot would carry more of the distribution, but the point of the chart
    is the comparison between the width of the bars and the vertical spread of
    the dots, and boxes make that harder to see rather than easier.
    """
    apply_house_style()
    d = summary.sort_values("median").reset_index(drop=True)
    fig, ax = plt.subplots(figsize=(7.6, 4.6))
    y = np.arange(len(d))

    non_operating = d["sector"].isin(NON_OPERATING_MARGIN_SECTORS)
    colours = [SERIES[1] if flag else SERIES[0] for flag in non_operating]

    ax.hlines(y, d["p10"], d["p90"], color=colours, linewidth=1.2, alpha=0.30)
    ax.hlines(y, d["q1"], d["q3"], color=colours, linewidth=4.0, alpha=0.55)
    ax.scatter(d["median"], y, color=colours, s=38, zorder=4)

    ax.set_yticks(y)
    ax.set_yticklabels([f"{s}  (n={n})" for s, n in zip(d["sector"], d["n"])],
                       fontsize=8.5, color=INK_SECONDARY)
    ax.xaxis.set_major_formatter(lambda v, _: f"{v:.0%}")
    ax.set_xlabel("EBITDA margin")
    ax.set_title("Sector explains a quarter of margin variation, not most of it")
    ax.grid(axis="y", visible=False)
    ax.grid(axis="x", visible=True)
    ax.set_xlim(-0.02, min(1.0, d["p90"].max() * 1.12))

    ax.text(
        0.98, 0.06,
        f"$\\eta^2$ = {decomp['eta_squared']:.2f}   $\\omega^2$ = {decomp['omega_squared']:.2f}\n"
        f"{decomp['share_within_group']:.0%} of margin variance sits within sectors",
        transform=ax.transAxes, ha="right", va="bottom", fontsize=8.5, color=INK,
    )
    # A legend rather than a callout: the two flagged sectors are not adjacent
    # on the axis, so an arrow to one of them would understate the point.
    handles = [
        plt.Line2D([], [], marker="o", linestyle="none", color=SERIES[0],
                   label="operating margin"),
        plt.Line2D([], [], marker="o", linestyle="none", color=SERIES[1],
                   label="rent or interest income, not an operating margin"),
    ]
    ax.legend(handles=handles, loc="lower right", bbox_to_anchor=(1.0, 0.16),
              handletextpad=0.4)

    _source_line(
        fig,
        SOURCE + f" Margin universe, n={decomp['observations']}. Dot = median, "
        "thick bar = interquartile range, thin bar = 10th-90th percentile.",
        y=-0.06,
    )
    save(fig, path)


def quality_versus_price(core: pd.DataFrame, primary: dict, path) -> None:
    """Earnings multiple against margin, with the fitted line and the misses.

    The size effect gets its own panel rather than being left to marker area.
    Area is a poor channel for reading an ordered effect, and size is the term
    the regression actually finds, so it should not be the harder of the two to
    see.
    """
    apply_house_style()
    d = core[["symbol", "ebitda_margin", "price_to_earnings", "market_cap",
              "sector"]].dropna()
    d = d[d["price_to_earnings"] <= config.FLAG_HIGH_PE]

    fig, (ax, ax2) = plt.subplots(
        1, 2, figsize=(9.4, 4.6), gridspec_kw={"width_ratios": [3.0, 1.15], "wspace": 0.30}
    )
    sizes = 12 + 90 * (np.log(d["market_cap"]) - np.log(d["market_cap"]).min()) / (
        np.log(d["market_cap"]).max() - np.log(d["market_cap"]).min()
    )
    ax.scatter(d["ebitda_margin"], d["price_to_earnings"], s=sizes, color=SERIES[0],
               alpha=0.38, linewidth=0, zorder=3)

    # Fitted line from the primary specification, evaluated at the sample median
    # size so the line is a slice through the surface rather than a second fit.
    terms = {t["term"]: t["coefficient"] for t in primary["terms"]}
    grid = np.linspace(d["ebitda_margin"].quantile(0.02), d["ebitda_margin"].quantile(0.98), 50)
    median_log_cap = float(np.log(core["market_cap"]).median())
    fitted = np.exp(
        terms["const"] + terms["w_ebitda_margin"] * grid
        + terms["w_log_market_cap"] * median_log_cap
    )
    ax.plot(grid, fitted, color=SERIES[7], linewidth=2.0, zorder=4)

    tagged = d.nlargest(3, "market_cap")
    extremes = pd.concat([d.nlargest(2, "price_to_earnings"), d.nlargest(2, "ebitda_margin")])
    labelled = pd.concat([tagged, extremes]).drop_duplicates(subset="symbol")
    ax.scatter(labelled["ebitda_margin"], labelled["price_to_earnings"], s=26,
               facecolor="none", edgecolor=INK, linewidth=0.9, zorder=5)
    _label_points(ax, labelled["ebitda_margin"], labelled["price_to_earnings"],
                  labelled["symbol"], fontsize=7.5, color=INK)

    ax.set_yscale("log")
    ax.set_yticks([5, 10, 20, 40, 80])
    ax.set_yticklabels(["5x", "10x", "20x", "40x", "80x"])
    ax.xaxis.set_major_formatter(lambda v, _: f"{v:.0%}")
    ax.set_xlabel("EBITDA margin")
    ax.set_ylabel("Trailing price / earnings")
    ax.set_title("Margin buys no premium; scale does")

    ax.text(0.98, 0.96,
            f"log P/E ~ margin + log size\n"
            f"margin  {terms['w_ebitda_margin']:+.2f}   size  {terms['w_log_market_cap']:+.2f}\n"
            f"R$^2$ = {primary['r_squared']:.3f}  (n = {primary['n']})",
            transform=ax.transAxes, ha="right", va="top", fontsize=8.5, color=INK)

    # Right panel: the size term, shown directly.
    quint = core[["market_cap", "price_to_earnings"]].dropna()
    quint["band"] = pd.qcut(quint["market_cap"], 5, labels=["1", "2", "3", "4", "5"])
    med = quint.groupby("band", observed=True)["price_to_earnings"].median()
    ax2.bar(np.arange(len(med)), med.to_numpy(), color=SEQUENTIAL[2], width=0.66)
    for i, v in enumerate(med.to_numpy()):
        ax2.annotate(f"{v:.0f}x", (i, v), xytext=(0, 3), textcoords="offset points",
                     ha="center", fontsize=7.5, color=INK_MUTED)
    ax2.set_xticks(np.arange(len(med)))
    ax2.set_xticklabels(["smallest", "", "", "", "largest"], fontsize=8)
    ax2.set_xlabel("Market capitalisation quintile")
    ax2.set_ylabel("Median P/E")
    ax2.set_title("Median multiple by size", fontsize=9.5)
    ax2.grid(axis="x", visible=False)
    ax2.set_ylim(0, med.max() * 1.22)

    _source_line(fig, SOURCE + " Core universe. Marker area scales with market "
                 "capitalisation; fitted line evaluated at the median size. "
                 f"P/E above {config.FLAG_HIGH_PE:.0f}x omitted from the scatter, retained in the fit.",
                 y=-0.055)
    save(fig, path)


def book_multiple_decomposition(decomp: dict, path) -> None:
    """Where the dispersion in the price-to-book multiple actually comes from."""
    apply_house_style()
    fig, ax = plt.subplots(figsize=(7.0, 3.0))

    parts = [
        ("Return on equity", decomp["share_from_roe"], SERIES[0]),
        ("Earnings multiple", decomp["share_from_earnings_multiple"], SERIES[2]),
        ("Covariance of the two", decomp["share_from_covariance"], SERIES[1]),
    ]
    left_pos, left_neg = 0.0, 0.0
    for label, share, colour in parts:
        start = left_pos if share >= 0 else left_neg + share
        ax.barh([0], [abs(share)], left=[start], color=colour, height=0.42)
        ax.annotate(f"{label}\n{share:+.0%}", (start + abs(share) / 2, 0),
                    xytext=(0, 30 if share >= 0 else -38), textcoords="offset points",
                    ha="center", fontsize=8.5, color=colour)
        if share >= 0:
            left_pos += share
        else:
            left_neg += share

    ax.axvline(0, color=AXIS, linewidth=0.9)
    ax.set_ylim(-0.9, 0.9)
    ax.set_yticks([])
    ax.set_xlim(-0.35, 1.25)
    ax.xaxis.set_major_formatter(lambda v, _: f"{v:.0%}")
    ax.set_xlabel("Share of the variance of log(price / book)")
    ax.set_title("Nine tenths of what looks like valuation is just return on equity")
    ax.grid(axis="y", visible=False)

    _source_line(
        fig,
        SOURCE + " Exact decomposition of log(P/B) = log(ROE) + log(P/E); "
        f"n = {decomp['n']}, maximum identity residual "
        f"{decomp['identity_max_abs_residual']:.1e}. "
        f"Correlation of log ROE with log P/E: {decomp['corr_log_roe_log_pe']:+.2f}.",
        y=-0.20,
    )
    save(fig, path)


def growth_gap(screened: pd.DataFrame, summary: dict, path) -> None:
    """Fundable growth against priced-in growth, with the disagreements named."""
    apply_house_style()
    s = screened[screened["in_screen"]].dropna(
        subset=["sustainable_growth", "priced_in_growth"]
    )
    fig, ax = plt.subplots(figsize=(7.4, 4.8))

    deficit = s["growth_gap"] < -config.GROWTH_GAP_THRESHOLD
    surplus = s["growth_gap"] > config.GROWTH_GAP_THRESHOLD
    consistent = ~(deficit | surplus)

    for mask, colour, label in (
        (consistent, INK_MUTED, "broadly consistent"),
        (surplus, SERIES[2], "can fund more than priced in"),
        (deficit, SERIES[1], "priced above what it can fund"),
    ):
        ax.scatter(s.loc[mask, "priced_in_growth"], s.loc[mask, "sustainable_growth"],
                   s=26, color=colour, alpha=0.55, linewidth=0, label=label, zorder=3)

    x_lo = min(s["priced_in_growth"].min(), 0) - 0.012
    y_hi = s["sustainable_growth"].max() * 1.12
    ax.plot([x_lo, 0.12], [x_lo, 0.12], color=INK_MUTED, linewidth=1.0,
            linestyle=(0, (4, 4)), zorder=2)
    ax.annotate("the two agree", (0.12, 0.12), xytext=(5, -3),
                textcoords="offset points", fontsize=7.5, color=INK_MUTED, rotation=30)

    # Surplus names are well spread, so they take point labels with alternating
    # offsets. The deficit names are not: they sit in a dense cluster a
    # percentage point wide, where point labels would overprint each other, so
    # they go into a list with a single leader to the cluster.
    surplus_named = s.nlargest(5, "growth_gap").sort_values("priced_in_growth")
    for i, row in enumerate(surplus_named.itertuples()):
        left = i % 2 == 1
        ax.annotate(row.symbol, (row.priced_in_growth, row.sustainable_growth),
                    xytext=(-6 if left else 6, 4), textcoords="offset points",
                    ha="right" if left else "left", fontsize=7.5, color=INK)

    deficit_named = s.nsmallest(5, "growth_gap")
    listing = "\n".join(
        f"{r.symbol}  {r.growth_gap:+.1%}" for r in deficit_named.itertuples()
    )
    ax.annotate(
        "Widest deficits\n" + listing,
        xy=(float(deficit_named["priced_in_growth"].median()),
            float(deficit_named["sustainable_growth"].median())),
        xytext=(0.135, 0.02), textcoords="data", ha="left", va="bottom",
        fontsize=7.5, color=SERIES[1],
        arrowprops=dict(arrowstyle="-", color=AXIS, linewidth=0.7, shrinkB=6),
    )

    ax.set_xlim(x_lo, 0.20)
    ax.set_ylim(-0.02, y_hi)
    ax.xaxis.set_major_formatter(lambda v, _: f"{v:.0%}")
    ax.yaxis.set_major_formatter(lambda v, _: f"{v:.0%}")
    ax.set_xticks(np.arange(-0.02, 0.13, 0.02))
    ax.set_yticks(np.arange(0, y_hi, 0.10))
    ax.set_xlabel(f"Growth the price requires at a {config.COST_OF_EQUITY:.0%} cost of equity")
    ax.set_ylabel("Growth the balance sheet can fund (ROE x retention)")
    ax.set_title("Where a company's own arithmetic disagrees with its price")
    ax.legend(loc="lower left", handletextpad=0.4)

    ax.text(0.985, 0.97,
            f"{summary['n_funding_deficit']} names priced above\n"
            f"what they can fund\n"
            f"{summary['n_funding_surplus']} the other way\n"
            f"{summary['screen_universe']} screened",
            transform=ax.transAxes, ha="right", va="top", fontsize=8.5, color=INK)

    _source_line(
        fig,
        SOURCE + f" Screen universe: core constituents with ROE below "
        f"{100 * 0.40:.0f}% and P/E below {config.FLAG_HIGH_PE:.0f}x — above those the "
        "identity stops describing a real constraint.",
        y=-0.055,
    )
    save(fig, path)


def peer_benchmark(peers: pd.DataFrame, sector: str, path, top: int = 18) -> None:
    """Margin, ROE and earnings-yield percentile ranks side by side."""
    apply_house_style()
    d = peers.nlargest(top, "market_cap").sort_values("composite_rank").reset_index(drop=True)
    fig, ax = plt.subplots(figsize=(7.6, 5.4))
    y = np.arange(len(d))

    cols = [("rank_margin", "EBITDA margin", SERIES[0]),
            ("rank_roe", "Return on equity", SERIES[2]),
            ("rank_earnings_yield", "Earnings yield", SERIES[3])]
    offsets = (-0.22, 0.0, 0.22)
    for (col, label, colour), off in zip(cols, offsets):
        ax.scatter(d[col], y + off, color=colour, s=34, label=label, zorder=3)

    for yi, row in zip(y, d.itertuples()):
        lo = min(row.rank_margin, row.rank_roe, row.rank_earnings_yield)
        hi = max(row.rank_margin, row.rank_roe, row.rank_earnings_yield)
        ax.hlines(yi, lo, hi, color=AXIS, linewidth=1.0, zorder=2)

    ax.axvline(0.5, color=INK_MUTED, linewidth=0.9, linestyle=(0, (4, 4)))
    ax.set_yticks(y)
    ax.set_yticklabels(d["symbol"], fontsize=8.5, color=INK_SECONDARY)
    ax.set_xlim(-0.03, 1.03)
    ax.xaxis.set_major_formatter(lambda v, _: f"{v:.0%}")
    ax.set_xlabel(f"Percentile rank within {sector}")
    ax.set_title(f"Few {sector} names rank well on quality and price at once")
    ax.grid(axis="y", visible=False)
    ax.grid(axis="x", visible=True)
    ax.legend(loc="lower right", ncol=1, handletextpad=0.4)

    _source_line(
        fig,
        SOURCE + f" {sector}, {top} largest core-universe constituents by market "
        "capitalisation, ordered by the unweighted composite of the three ranks. "
        "Dashed line is the sector median.",
        y=-0.05,
    )
    save(fig, path)


def cost_of_equity_sensitivity(sweep: pd.DataFrame, path) -> None:
    """What moves, and what does not, when the discount rate assumption changes."""
    apply_house_style()
    fig, ax = plt.subplots(figsize=(7.2, 4.0))
    x = sweep["cost_of_equity"]
    width = 0.004

    ax.bar(x - width / 2, sweep["n_funding_deficit"], width=width, color=SERIES[1],
           label="priced above what it can fund")
    ax.bar(x + width / 2, sweep["n_funding_surplus"], width=width, color=SERIES[2],
           label="can fund more than priced in")

    for xi, lo, hi in zip(x, sweep["n_funding_deficit"], sweep["n_funding_surplus"]):
        ax.annotate(f"{lo}", (xi - width / 2, lo), xytext=(0, 3),
                    textcoords="offset points", ha="center", fontsize=7.5, color=INK_MUTED)
        ax.annotate(f"{hi}", (xi + width / 2, hi), xytext=(0, 3),
                    textcoords="offset points", ha="center", fontsize=7.5, color=INK_MUTED)

    ax.set_xticks(x)
    ax.xaxis.set_major_formatter(lambda v, _: f"{v:.0%}")
    ax.set_xlabel("Assumed cost of equity")
    ax.set_ylabel("Constituents flagged")
    ax.set_title("The assumption moves the count and leaves the ranking untouched")
    ax.grid(axis="x", visible=False)
    ax.legend(loc="upper right", ncol=1, handletextpad=0.4)
    ax.set_ylim(0, sweep[["n_funding_deficit", "n_funding_surplus"]].to_numpy().max() * 1.52)

    corr = sweep["rank_corr_vs_base"].min()
    ax.text(0.01, 0.97,
            f"Rank correlation against the {config.COST_OF_EQUITY:.0%} base case:\n"
            f"{corr:.3f} at every rate tested",
            transform=ax.transAxes, va="top", fontsize=8.5, color=INK)

    _source_line(
        fig,
        SOURCE + " Priced-in growth is r - (E/P) x b, so a change in r shifts every "
        "company by the same constant and cannot reorder them.",
        y=-0.05,
    )
    save(fig, path)
