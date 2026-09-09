# Fundamentals dashboard — build notes

The report answers the question once. The dashboard lets an analyst re-ask it of
a different sector, a different cost of equity, or a single company, without
going back to the pipeline.

The extracts in `extracts/` are written by `make analysis` and are the only
inputs — no manual reshaping between the pipeline and the dashboard.

**Live dashboard:** https://lohandesilva.github.io/lohan-desilva-portfolio/dashboards/sp500.html

The dashboard is built and hosted directly rather than through a BI tool, so it
has no third-party account behind it and no refresh to keep alive: it reads the
same extracts this pipeline writes, and the page is a single self-contained file.

The Tableau build below is kept as a specification. It is the same data model and
the same measure definitions, so the workbook can be rebuilt in Tableau or, with
the DAX equivalents in `calculated-fields.md`, in Power BI on a Windows machine.


---

## Data model

Four flat extracts, unjoined. Each drives a different sheet. A star schema would
be overkill for a single-entity dataset, and flattening keeps the refresh to one
step.

| File | Grain | Rows | Drives |
|---|---|---|---|
| `fct_constituent_fundamentals.csv` | one row per constituent | 503 | KPI tiles, scatter plots, the company list |
| `agg_sector_margins.csv` | one row per sector | 11 | margin dispersion chart |
| `dim_peer_benchmark.csv` | one row per core-universe constituent | 354 | peer ranking sheet |
| `agg_cost_of_equity_sweep.csv` | one row per assumed rate | 6 | sensitivity sheet |

`fct_constituent_fundamentals.csv` carries every derived fundamental alongside the
raw ratios, plus the four universe flags and the screen output. Nothing is
recomputed in Tableau that the pipeline already computes: a percentile rank
recalculated inside a workbook changes the moment anyone applies a filter, which
is not what a rank against a fixed peer set means.

## The universe flags are the most important fields in the extract

`in_base`, `in_margin`, `in_returns`, `in_core`. Every sheet must filter to one of
them explicitly, and the sheet title should say which. This is the single thing
most likely to go wrong in a rebuild.

The reason is that the four universes have genuinely different sizes — 483, 455,
380 and 354 — and a number computed on the wrong one is plausible rather than
obviously broken. A median EBITDA margin computed on `in_core` instead of
`in_margin` is not an error anyone will spot by looking at it.

Set the universe filter as a context filter so it applies before any FIXED
level-of-detail expression. Applied afterwards, a LOD anchored to the whole table
will quietly include the excluded rows.

## Sheets

**1. Position (KPI row).** Six tiles: constituents, index market capitalisation,
aggregate EBITDA margin, aggregate net margin, median ROE, cap-weighted P/E.

The two P/E tiles — median and cap-weighted — sit side by side deliberately. The
gap between them is the weight of the largest companies, and showing either alone
hides it.

**2. Margin dispersion by sector.** Horizontal, sorted by median descending, with
the interquartile range as a Gantt bar and the median as a circle. Colour flags
Financials and Real Estate, whose margins are not comparable to an operating
company's. Add the eta-squared as a caption rather than a mark — it is a
property of the whole chart, not of any bar.

Do **not** offer a "sort by sector name" option. Alphabetical order on a
dispersion chart is how a reader loses the finding.

**3. Quality versus price.** Scatter, EBITDA margin on columns, P/E on rows with
a logarithmic axis, market capitalisation on size. Add a trend line (linear, on
the log axis) and show the R² in the tooltip rather than on the chart, so nobody
reads 0.09 as a fit.

Filter the plotted range to P/E below 100x with a note. Leaving CrowdStrike at
5,085x in the view compresses every other point into a band.

**4. Growth screen.** Scatter of fundable growth against priced-in growth, with a
45° reference line, coloured on the three-way verdict. The cost-of-equity
parameter drives the x-axis; the ranking will not move, which is worth
demonstrating live rather than asserting.

**5. Peer benchmark.** Three percentile-rank measures on a shared axis, one row
per company, filtered to a selected sector. Sorted by the composite. A reference
line at 0.5 is the sector median.

**6. Company list.** The action layer: symbol, name, sector, market cap, margin,
ROE, P/E, growth gap, and the exclusion reason where there is one. Sorted by
market capitalisation descending. Keep the excluded rows visible with their
`fail_reasons` string — an analyst who cannot see why a company is missing will
assume the data is broken.

## Dashboard layout

Fixed size, 1200 × 900. Tiled, not floating — floating layouts break on every
screen that is not the author's.

```
┌─────────────────────────────────────────────────────────┐
│  KPI row (6 tiles)                                      │
├──────────────────────────────┬──────────────────────────┤
│  Margin dispersion by sector │  Quality versus price    │
├──────────────────────────────┴──────────────────────────┤
│  Growth screen    │  Company list (scrollable)          │
└─────────────────────────────────────────────────────────┘
```

Filters: sector, sub-industry, universe flag, market-cap band. Parameters: cost
of equity, terminal payout, gap threshold. Keep them in a single row above the
charts rather than in a right-hand rail — a vertical filter rail costs 200px of
chart width for four controls.

Put the cost-of-equity parameter next to a caption showing the rank correlation
against the base case. It is 1.000 at every rate, and a user who moves the slider
should see that the ordering does not move with it.

## Colour

The workbook uses the same palette as the report figures so the two read as one
document:

| Role | Hex |
|---|---|
| Primary series | `#2a78d6` |
| Flagged / deficit | `#eb6834` |
| Positive / surplus | `#1baf7a` |
| Tertiary series | `#eda100` |
| Grid | `#e1e0d9` |
| Body text | `#52514e` |

Set these once as a custom palette in `Preferences.tps` rather than picking them
per sheet.

## Publishing

Tableau Public only accepts extracts, not live connections, so `make analysis`
then re-upload. Keep the file names stable — Tableau Public re-maps the data
source on every filename change and silently breaks calculated fields that
reference the old name.

## Why not Power BI

Power BI Desktop does not run on macOS, and browser authoring in the Power BI
Service cannot produce a publicly shareable report on the free tier. The
measure definitions in `calculated-fields.md` include DAX equivalents, so the
same model can be rebuilt in Power BI on a Windows machine without redoing the
thinking.
