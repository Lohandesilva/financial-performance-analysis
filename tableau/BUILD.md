# Tableau build

Four sheets, two calculated fields, one dashboard. Around forty minutes the
first time.

The three CSVs here are shaped for Tableau rather than for analysis. The
constituent file is already screened and carries every derived ratio the
workbook needs, the sector file is at its reporting grain, and the funding-gap
list is already filtered and sorted. Tableau does presentation, not arithmetic.

| File | Rows | Grain |
|---|---|---|
| `1_constituents.csv` | 354 | one row per company in the core universe |
| `2_sector_margins.csv` | 11 | one row per GICS sector |
| `3_funding_gap.csv` | 69 | companies priced above the growth they can fund |

The source extract has no income statement. Revenue, EBITDA, net income and book
equity are all reconstructed from price and the published ratios using accounting
identities, and the reconstruction reconciles to within 1.4e-7 relative error.
That is worth a line on the dashboard, because a reader who assumes these are
reported figures will draw a stronger conclusion than the data supports.

---

## Connect

1. Open **Tableau Public**. Check the title bar says "Tableau Public", not
   "Tableau".
2. **Connect → To a File → Text file** → `1_constituents.csv`. Rename the
   connection `Constituents`.
3. Bottom-left **⊕** → **New Data Source** → add `2_sector_margins.csv`, then
   `3_funding_gap.csv`.
4. Click **Sheet 1**.

## Two calculated fields

On the **Constituents** source.

**`Aggregate Net Margin`**

```
SUM([Net Income]) / SUM([Revenue])
```

**`Cap-Weighted P/E`**

```
SUM([Market Cap]) / SUM([Net Income])
```

Format the first as **Percentage, 1 decimal**; the second as **Number, 1
decimal**.

Both are deliberately aggregate rather than averaged. A simple average of P/E
across 354 companies is dominated by whichever handful trade on thin earnings —
it is a statistic about the tail, not about the index. Summing the numerator and
the denominator first gives the multiple an investor would actually pay for the
whole basket, which is the question being asked.

Keep `MEDIAN([Net Margin])` and `MEDIAN([P/E])` available too. The aggregate and
the median answer different questions — "what does the index cost" versus "what
does a typical constituent look like" — and having both on the page is the point.

**Check before going further.** Drag `Aggregate Net Margin` onto **Text**:
**14.7%**. Swap for `Cap-Weighted P/E`: **26.1**. Clear the sheet.

## Sheet 1 — Position

Name it `Position`.

1. `Measure Names` → **Rows**, `Measure Values` → **Text**.
2. Keep only: `Number of Records` (rename it `Companies` on the card),
   `Market Cap`, `Revenue`, `Net Income`, `Aggregate Net Margin`,
   `Cap-Weighted P/E`. Then add `MEDIAN([ROE])` and `MEDIAN([P/E])`.

Expect: 354 companies · $56.6tn market cap · $14.77tn revenue · $2.17tn net
income · 14.7% · 26.1 · median ROE **18.1%** · median P/E **24.2**.

Median ROE of 18.1% against a cap-weighted P/E of 26.1 is the tension the rest of
the workbook unpacks: the index is not obviously cheap, and it is not obviously
low-quality either.

## Sheet 2 — Margin dispersion by sector

Name it `Sector Margins`. Switch to **2_sector_margins**.

1. `Sector` → **Rows**
2. `Measure Values` → **Columns**; in the card keep only `P10`, `Q1`,
   `Median EBITDA Margin`, `Q3`, `P90`.
3. `Measure Names` → **Colour**. Marks type → **Circle**. Size down to about a
   third of default.
4. Sort `Sector` by `Median EBITDA Margin` descending — click the sort icon on
   the row header.

Expect Real Estate highest at a median of **60.2%**, and every sector to show a
visible spread rather than a point.

This is a strip plot rather than a box plot on purpose. Tableau's built-in box
plot recomputes quartiles from whatever rows are in the view; these percentiles
were computed once, in the pipeline, over the full 455-company margin universe,
and they should not move when someone filters the dashboard.

The finding is the width of these strips, not their position. Sector explains
**26%** of the variance in EBITDA margin (η² = 0.261, ω² = 0.244) — so **74%** of
it sits *within* sectors. "Compare a company to its sector median" is therefore
a much weaker benchmark than it is usually treated as.

## Sheet 3 — Quality against price

Name it `Quality Vs Price`. Switch back to **Constituents**.

1. `ROE` → **Columns**, `Earnings Yield` → **Rows**. Right-click each pill →
   **Dimension** so you get one mark per company rather than one aggregated dot.
2. `Symbol` → **Detail**, `Sector` → **Colour**, `Market Cap` → **Size**.
3. Analytics tab → drag **Trend Line** → **Linear** onto the view.
4. Filter `ROE` to **0 to 0.4** and `Earnings Yield` to **0 to 0.12** so the
   axes are set by the body of the distribution rather than by four outliers.
   State the filter in the caption — a trimmed axis that isn't disclosed is the
   kind of thing that gets a chart dismissed.

The trend line will be flat and Tableau will report an R² of about **0.000**.

A note on that number, because someone will ask: the published figure in the
report is **R² = 0.002**, from a market-cap-weighted regression of earnings yield
on ROE and net margin. Tableau's trend line is unweighted, so it lands slightly
lower. Both say the same thing — there is no relationship — but they are not the
same statistic, and it is worth being able to say which is which.

The point of the sheet is the absence: profitability does not predict what the
market charges for earnings. What does predict it is size — adding log market cap
to the regression takes R² from 0.008 to **0.091**.

## Sheet 4 — Priced above what the balance sheet can fund

Name it `Funding Gap`. Switch to **3_funding_gap**.

1. Onto **Rows**, in order: `Symbol`, `Company`, `Sector`, `Market Cap`, `ROE`,
   `Payout Ratio`, `Sustainable Growth`, `Priced In Growth`, `Growth Gap`, `P/E`.
2. Any green pill → **Dimension**.
3. Sort by `Growth Gap` **ascending** — most negative first.

Expect **69** companies of the 285 in the screen (24.2%), carrying **$4.24tn** of
market capitalisation. Their median payout is **66.2%** against a median ROE of
**8.8%**; the 165 companies on the other side of the screen pay out 22.3% on an
ROE of 21.2%.

`Growth Gap` is sustainable growth minus the growth the current price implies at
a 9% cost of equity. Negative means the market is paying for growth the company
cannot fund out of retained earnings. The ±2 percentage point dead band around
zero is the threshold used throughout the report, and 51 companies land inside it.

This is a screen, not a verdict. A company can fund growth by issuing equity or
debt, and this test sees neither. Say that on the dashboard.

## Dashboard

1. New **Dashboard** → Size → **Fixed size → 1200 × 900**, tiled not floating.

```
┌──────────────────────────────────────────────┐
│  Position                                    │
├───────────────────────┬──────────────────────┤
│  Sector Margins       │  Quality Vs Price    │
├───────────────────────┴──────────────────────┤
│  Funding Gap                                 │
└──────────────────────────────────────────────┘
```

2. Each sheet → **▾ → Fit → Entire View**.
3. Filters: click `Quality Vs Price` → ▾ → **Filters** → add `Sector`. Card → ▾ →
   **Apply to Worksheets → All Using This Data Source**.
4. Dashboard menu → **Show Title** → `S&P 500 Profitability and Valuation`.
5. Add a **Text** object under the title: *"Fundamentals reconstructed from
   published ratios by accounting identity — the source extract carries no income
   statement. 354-company core universe; 285 in the growth screen."*

## Publish

**File → Save to Tableau Public As…** → name it
`S&P 500 Profitability and Valuation`.

**Edit Details** on the published page:

> Profitability and valuation across the S&P 500, with every fundamental
> reconstructed from published ratios. Sector explains only a quarter of margin
> variation, and the market pays for size rather than quality. Full analysis,
> method and code: github.com/Lohandesilva/financial-performance-analysis

## Two things not to do

**Do not use Tableau's box plot on the sector sheet.** It would recompute
quartiles from the rows in view, which silently contradicts the percentiles the
report quotes.

**Do not put P/E on a log axis without saying so.** It is often the right choice
here — the distribution is heavily right-skewed — but an undisclosed log axis
makes a wide dispersion look tight, and that is the opposite of this workbook's
argument.
