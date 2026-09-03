# Calculated fields

Tableau syntax, with the DAX equivalent where the two differ in a way that
matters. Field names match the column headers in `extracts/`.

---

## Universe filters

Every sheet filters to exactly one universe, and every one of these must be set
as a **context filter** so it applies before any FIXED level-of-detail
expression. Applied after, a FIXED LOD anchored to the whole table silently
includes the excluded rows.

```
[In Core]        // 354 rows: regression, growth screen, peer ranks
[In Margin]      // 455 rows: EBITDA margin work
[In Returns]     // 380 rows: ROE and payout work
[In Base]        // 483 rows: denominators and index weights
```

The four are nested, not alternatives. `In Core` is `In Margin AND In Returns`.

**Excluded, with reason** — for the company list, so a missing name is visibly
missing rather than mysteriously absent:

```
IF NOT [In Core] THEN [Fail Reasons] ELSE "" END
```

---

## Position measures

**Aggregate EBITDA margin** — a ratio of sums, never an average of ratios

```
SUM([Ebitda]) / SUM([Revenue])
```
```dax
Aggregate EBITDA Margin = DIVIDE(SUM(fct[ebitda]), SUM(fct[revenue]))
```

The average of a ratio is not the ratio of the averages, and the difference here
is several points. `AVG([Ebitda Margin])` gives every company equal weight, which
answers a different question and should be named differently when it is wanted.

**Median EBITDA margin** — the typical constituent, as opposed to the index

```
MEDIAN([Ebitda Margin])
```

Report this next to the aggregate. The gap between them is the weight of the
largest companies and is itself a finding.

**Cap-weighted P/E**

```
SUM([Market Cap]) / SUM([Net Income])
```
```dax
Cap Weighted PE = DIVIDE(SUM(fct[market_cap]), SUM(fct[net_income]))
```

Not `AVG([Price To Earnings])`. Averaging multiples across companies gives the
richest names a weight they have not earned and produces a number several turns
above the truth.

---

## Derived fundamentals

These arrive pre-computed in the extract. The definitions are repeated here so
that anyone rebuilding the model in a tool without the pipeline gets the same
answers, and so the algebra is visible at the point of use.

**Return on equity** — `(P/B) / (P/E) = (P/B) × (E/P) = E/B`

```
[Price To Book] / [Price To Earnings]
```

Price cancels. This is why ROE derived this way carries no valuation information
of its own, and why regressing a multiple against it is circular.

**Payout ratio** — `(D/P) × (P/E) = D/E`

```
[Dividend Yield] * [Price To Earnings]
```

**Retention ratio**

```
1 - [Payout Ratio]
```

**Sustainable growth** — the Gordon identity, `ROE × retention`

```
[Roe] * (1 - [Payout Ratio])
```
```dax
Sustainable Growth = AVERAGE(fct[roe]) * (1 - AVERAGE(fct[payout_ratio]))
```

Row-level in Tableau, so it aggregates correctly under any grouping. In DAX the
same expression at the measure level would average the components first, which is
wrong; use `SUMX` over the table if the measure must aggregate.

**Earnings yield**

```
1 / [Price To Earnings]
```

---

## Growth screen

Parameters: `Cost Of Equity` (default 0.09), `Terminal Payout` (default 0.45),
`Gap Threshold` (default 0.02).

**Priced-in growth** — Gordon inverted at a constant terminal payout

```
[Cost Of Equity] - [Earnings Yield] * [Terminal Payout]
```

The payout term is not optional. The shortcut `[Cost Of Equity] - [Earnings
Yield]` assumes full distribution and makes every retaining company look as if
the market demanded impossible growth from it.

**Growth gap**

```
[Sustainable Growth] - [Priced In Growth]
```

**Verdict**

```
IF   [Growth Gap] < -[Gap Threshold] THEN "priced above what it can fund"
ELSEIF [Growth Gap] >  [Gap Threshold] THEN "can fund more than priced in"
ELSE "broadly consistent"
END
```

**Screen eligibility** — two exclusions beyond the core universe

```
[In Core] AND [Roe] <= 0.40 AND [Price To Earnings] <= 100
```

Above a 40% return on equity the sustainable-growth identity stops describing a
real constraint: buybacks have shrunk book equity towards zero, so ROE rises
without the capacity to grow rising with it. Above 100x earnings the earnings
yield is near zero and the gap is a statement about the denominator. Both are
judgement calls and both belong on the dashboard as a visible note, not buried in
a filter.

**Rank stability caption** — put this next to the cost-of-equity slider

```
"Ranking is invariant to this parameter: g_priced = r - (E/P) x b, "
+ "so a change in r shifts every company by the same constant."
```

The count of flagged names moves from 34 at a 7% cost of equity to 103 at 12%.
The ordering does not move at all. A user moving the slider should be able to see
that.

---

## Peer benchmarking

Ranks are computed **in the pipeline**, not in Tableau, and arrive in
`dim_peer_benchmark.csv`. A `RANK_PERCENTILE` table calculation recomputes itself
whenever a filter changes, which means a company's "rank against its sector"
would silently become its rank against whatever is left on screen.

If the rank must be rebuilt in-tool anyway:

```
RANK_PERCENTILE(AVG([Ebitda Margin]))
```

Set *Compute Using* to the company dimension, partitioned by sector. Then verify
against `dim_peer_benchmark.csv` before publishing, because getting the partition
wrong produces a plausible number.

**Composite rank**

```
([Rank Margin] + [Rank Roe] + [Rank Earnings Yield]) / 3
```

Equal weights are a decision, not a result. Expose the three components on the
sheet so a user can reweight by eye.

**Classification**

```
IF   [Rank Margin] >= 0.5 AND [Rank Roe] >= 0.5 AND [Rank Earnings Yield] >= 0.5
     THEN "quality at a discount"
ELSEIF [Rank Margin] >= 0.5 AND [Rank Roe] >= 0.5
     THEN "quality, fully priced"
ELSEIF [Rank Earnings Yield] >= 0.5
     THEN "cheap on price alone"
ELSE "expensive without the quality"
END
```

---

## Dispersion

**Within-sector IQR** — the bar length on the dispersion chart

```
{ FIXED [Sector] : PERCENTILE([Ebitda Margin], 0.75) }
- { FIXED [Sector] : PERCENTILE([Ebitda Margin], 0.25) }
```
```dax
Within Sector IQR =
VAR S = VALUES(fct[sector])
RETURN
    PERCENTILEX.INC(CALCULATETABLE(fct, S), fct[ebitda_margin], 0.75)
  - PERCENTILEX.INC(CALCULATETABLE(fct, S), fct[ebitda_margin], 0.25)
```

**Share of index market capitalisation** — must survive filtering

```
SUM([Market Cap]) / { FIXED : SUM(IF [In Base] THEN [Market Cap] END) }
```
```dax
Share Of Index Cap =
DIVIDE(
    SUM(fct[market_cap]),
    CALCULATE(SUM(fct[market_cap]), fct[in_base] = TRUE, ALL(fct))
)
```

The `FIXED` LOD (and `ALL()` in DAX) anchors the denominator to the whole index.
Without it the share reads 100% for whatever selection is active, which looks
plausible and is wrong. Note the `In Base` condition inside the denominator: the
raw file double-counts three dual-class companies, so an unfiltered total
overstates the index by about six percent.

**Non-operating margin flag** — for colour on the dispersion chart

```
IF [Sector] = "Financials" OR [Sector] = "Real Estate" THEN "flagged" ELSE "operating" END
```

Banks report interest income and REITs report rent against a depreciating asset
base. Neither margin is comparable to an operating company's, and leaving them
unmarked is what makes the sector effect look larger than it is.
