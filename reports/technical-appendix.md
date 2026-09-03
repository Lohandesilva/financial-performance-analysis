# Technical appendix

Derivations, method, and the places where the analysis could be wrong.

## 1. Source and scope

S&P 500 constituent financials published by the Frictionless Data project: 503
rows, 14 fields, one per index constituent. Symbol, name, GICS sub-industry,
price, trailing P/E, dividend yield, trailing EPS, the 52-week range, market
capitalisation, EBITDA, price-to-sales, price-to-book and an EDGAR link.

Three absences set the boundaries of what can be concluded:

**No date.** The file carries no as-of column and the publisher overwrites it in
place, so the vintage cannot be read off and has to be inferred from the prices.
Everything here is one point in time. Nothing should be quoted as a current
market level, and no comparison to a prior period is possible.

**No income statement or balance sheet.** Every fundamental is reconstructed from
the ratios (§3). The reconstructions are exact identities, not estimates, but
they inherit any inconsistency in the ratio inputs.

**No forecasts.** All earnings are trailing. Where the analysis needs a
forward-looking quantity — the growth a price implies — it is derived from a
stated model with a stated cost of equity, not from consensus.

There is one internal clue to how the file was assembled. Seventeen constituents
carry no market data at all, and several of them are companies that have left the
index through acquisition or take-private — Hess, Catalent and Marathon Oil among
them. The constituent roster and the price vector were therefore struck at
different times, which is a caution about the roster rather than about the prices.

## 2. The sub-industry problem

The column the source labels `Sector` is GICS **sub-industry**: 127 distinct
values across 503 rows, a median of two constituents each.

This is not a cosmetic mislabelling. A one-way ANOVA on 127 groups and roughly
370 usable observations is fitting 126 parameters, and it will report a large
eta-squared on noise. The analysis therefore rolls sub-industry up to the eleven
GICS sectors (`src/sectors.py`) and reports both levels, with the bias-corrected
omega-squared alongside eta-squared at each.

The mapping raises on an unmapped value rather than defaulting to "Other",
because a new constituent silently bucketed into a residual group would distort
exactly the between-group comparison the analysis rests on. Two assignments
moved in the March 2023 GICS revision and are still commonly mis-mapped:
Transaction & Payment Processing Services (Visa, Mastercard) sits in Financials,
and Data Processing & Outsourced Services (Broadridge) in Industrials.

## 3. Derivations

Every fundamental below is an algebraic rearrangement, exact wherever the vendor
struck the multiple and the market capitalisation on the same accounts.
Implemented in `src/derive.py` and again in `sql/01_staging.sql`.

Notation: `P` price, `M` market capitalisation, `S` shares, `E` earnings,
`B` book equity, `D` dividends.

**Shares outstanding.** `S = M / P`. True by the definition of market
capitalisation.

**Revenue.** `Revenue = M / (P/Sales)`. Price-to-sales is quoted per share, but
the per-share terms cancel: `P/Sales = (M/S) / (Rev/S) = M / Rev`. So dividing
market capitalisation by the multiple returns total revenue, not revenue per
share. The same cancellation gives **book equity** = `M / (P/B)`.

**Net income.** `E = EPS × S`.

**Return on equity.** `ROE = (P/B) / (P/E)`.

    (P/B) ÷ (P/E) = (P/B) × (E/P) = E/B

Price cancels completely. This is the point that makes the rest of the valuation
work possible and constrains it at the same time: ROE is a *fundamental* ratio
derived entirely from two *market* ratios, so it carries no valuation content of
its own but is not independent of the multiples either. See §5.

**Payout ratio.** `payout = (D/P) × (P/E) = D/E`. Price cancels again.
**Retention** is `1 − payout`.

**Earnings yield.** `E/P = 1 / (P/E)`.

**Sustainable growth.** `g = ROE × (1 − payout)`. Equity grows only by earnings
retained, so the fastest a company can grow without issuing equity or adding
leverage is the return it earns on book times the fraction it keeps. This is an
upper bound on organic growth, not a forecast.

**Priced-in growth.** Gordon with a constant payout `b` on earnings:

    P = (E × b) / (r − g)    ⟹    g = r − (E/P) × b

The payout term matters. The shortcut `g = r − E/P` assumes full distribution and
would make every retaining company look as though the market demanded impossible
growth from it. A single long-run market payout is used rather than each
company's own, because the question is what the *market* prices under a common
terminal assumption; using each firm's current payout would fold company
distribution policy into a number meant to isolate price.

**The reconciliation check that turned out to be a tautology.** Net income can be
reached two ways: `EPS × S`, and `M / (P/E)`. They should agree if every field
was struck on the same accounts. They agree to 1.4 × 10⁻⁷ here — which validates
nothing, because the vendor computes P/E as `price ÷ EPS` (asserted directly in
`sql/01_staging.sql`), making the two routes the same expression rearranged. The
check is retained as a tripwire: if the source ever starts sourcing P/E
independently, a real gap will appear rather than propagate silently.

## 4. Screening and exclusions

Applied in `src/ingest.py`, logged to `outputs/metrics.json` under
`data_quality`, and listed row by row in
`outputs/tables/excluded_constituents.csv`.

The screen removes observations where a derived quantity is **undefined or
arithmetically impossible**, never observations that are merely extreme. A
company on 90x earnings is expensive, not wrong, and excluding it would select
the sample towards the conclusion. Extreme-but-real values are flagged, retained,
and winsorised in the regression only.

Three nested universes come out of it, rather than one "clean" table. A company
with negative book equity is unusable for ROE and perfectly usable for an EBITDA
margin; collapsing both decisions into a single filter loses observations for no
reason.

Shares below are against base-universe market capitalisation ($66.58tn), not
the raw file total — the file double-counts the three dual-class companies.

| Universe | Companies | Share of base market cap | Used for |
|---|---|---|---|
| Base | 483 | 100% | denominators, sector weights |
| Margin | 455 | 94.0% | §1 profitability dispersion |
| Returns | 380 | 90.8% | ROE and payout work |
| Core | **354** | **85.1%** | regression, growth screen, peer table |

**Rule counts.** These overlap — a row can trip several at once — so they sum to
more than the 129 companies the core universe loses.

| Rule | Rows | Why |
|---|---|---|
| No market data | 17 | Every numeric field null |
| Dual-class secondary | 3 | GOOG, FOX, NWS: one set of accounts, two listings |
| Negative trailing EPS | 28 | No earnings yield; ROE identity returns the wrong sign |
| P/E missing on a profitable company | 17 | Vendor coverage gap |
| Non-positive book equity | 32 | Inverts the ROE identity |
| Price-to-book missing | 21 | — |
| Book near zero (P/B > 250) | 4 | E/B numerically unstable |
| Payout above earnings | 40 | Retention, and so `g`, turns negative |
| EBITDA not reported | 43 | Structural; see below |
| EBITDA margin outside ±100% | 1 | Input error, not a margin |

Three of these are not data faults and should be read as findings.

**Missing P/E is not missingness.** The source never reports a negative P/E: where
trailing EPS is negative it nulls the multiple instead. All 28 rows with a
missing P/E and a present price have negative EPS. Treating that as random
missingness would bias the retained sample towards profitability — which it does,
and which is stated as a limitation rather than corrected, because the extract
carries no way to correct it.

**Missing EBITDA is structural.** The 43 rows are almost entirely banks, brokers
and asset managers, for whom interest expense is a cost of goods rather than a
financing item and EBITDA is not a meaningful measure. Their absence from the
margin universe is correct, not a gap.

**Negative book equity is an accounting fact, not an error.** Thirty-two
constituents — McDonald's, Philip Morris, Starbucks, Lowe's, HP, AutoZone,
Domino's and 25 others — have repurchased more equity than they have retained.
The ROE identity does not fail because the data is bad. It fails because book
equity has stopped being a meaningful denominator, which is worth knowing before
anyone screens on ROE.

**Dividend yield.** Blank on 104 rows. In this source that means no dividend
recorded, not unknown: every payer has the field populated. Filled with zero and
the count logged, so the call can be disagreed with.

## 5. Model specification

### 5.1 The entanglement problem

Most quality measures recoverable from this extract are algebraic rearrangements
of the valuation multiples:

    ROE        = (P/B) / (P/E)
    net margin = EPS × (P/S) / P = (E/P) × (P/S)

Regressing a multiple on either is regressing a variable on a function of itself,
and any R² that results is not evidence about investor behaviour.

**EBITDA margin is the exception.** EBITDA arrives as an absolute currency figure
and revenue is `M / (P/S)`, so the price terms cancel and what remains is a pure
fundamental. It is the only quality measure in this dataset carrying information
the multiples do not already contain, and it is therefore the regressor in the
primary specification.

### 5.2 Specifications fitted

OLS, `statsmodels`, inputs winsorised at the 1st and 99th percentiles (regression
only — never the reported medians). Winsorisation is there because a P/E of
5,085 is a real observation about a company with almost no trailing earnings and
belongs in the reported distribution, but would set the slope on its own in an
unweighted fit.

| Specification | n | R² | Adj. R² |
|---|---|---|---|
| Earnings yield ~ ROE + net margin (entangled) | 354 | 0.002 | −0.004 |
| log P/E ~ EBITDA margin | 354 | 0.008 | 0.005 |
| **log P/E ~ EBITDA margin + log size** | **354** | **0.091** | **0.086** |
| log P/E ~ + sustainable growth | 354 | 0.098 | 0.090 |
| log P/E ~ + sector fixed effects | 354 | 0.245 | 0.218 |
| log P/B ~ ROE + log size (mechanically linked) | 354 | 0.639 | 0.637 |

Primary specification coefficients:

| Term | Coefficient | Std. error | t | p |
|---|---|---|---|---|
| EBITDA margin | −0.607 | 0.198 | −3.07 | 0.002 |
| log market capitalisation | +0.144 | 0.025 | +5.67 | <0.001 |

The entangled specification is fitted and reported precisely because of what it
does not find: R² = 0.002, neither term significant. The worry going in was that
the algebraic dependence would manufacture a spurious fit. It does not, because
the third term in the identity (P/B) varies enough to break it. That is worth
knowing before anyone reads the 0.639 on the last row as evidence.

### 5.3 What the residuals mean

`outputs/tables/valuation_residuals.csv` lists the twenty companies the primary
specification misses by the most, both directions. A residual here is the gap
between the multiple a company trades on and the multiple its margin and size
predict. **It is not a signal.** The model explains 9% of the variation, so 91%
of every residual is things the model does not contain — growth, cyclical
position, capital structure, whether trailing earnings are representative. The
richest residuals are dominated by companies with almost no trailing earnings
(Molina at 1,266x, CrowdStrike at 5,085x), where the multiple is a statement
about a small denominator. The cheapest are dominated by insurers, utilities and
cable, where trailing earnings are high relative to what the market expects to
persist. The table is a starting point for questions.

### 5.4 Variance decomposition of the book multiple

Not a model. Taking logs of the ROE identity:

    log(P/B) = log(ROE) + log(P/E)

exact to 8.9 × 10⁻¹⁶ across the 354-company core universe, so

    var[log(P/B)] = var[log(ROE)] + var[log(P/E)] + 2·cov[log(ROE), log(P/E)]
    0.8479        = 0.7717        + 0.4531        + (−0.3769)

giving 91.0% / 53.4% / −44.4%. Correlation of log ROE with log P/E: **−0.32**.
This settles the "does the market pay for quality" question more cleanly than any
regression can here, because it involves no fitting and no assumptions.

## 6. The growth screen

`src/screen.py`. Fundable growth (`ROE × retention`) against priced-in growth
(`r − (E/P) × b`), with a company flagged when the two differ by more than two
percentage points.

**Two exclusions inside the screen, beyond the core universe.**

*Return on equity above 40% (60 companies).* Above that level the Gordon identity
stops describing a real constraint: sustained buybacks shrink book equity towards
zero, so ROE rises without the capacity to grow rising with it. Mastercard's
derived ROE is 284%, which is arithmetically correct and returns a sustainable
growth rate of 229%. The 40% threshold is a judgement — it sits at the 83rd
percentile of core-universe ROE — and it is stated rather than tuned.

*P/E above 100x (9 further companies).* The earnings yield is then close to zero,
so priced-in growth is pinned at the cost of equity and the gap is a statement
about the denominator rather than about the business.

That leaves **285 companies screened: 69 in deficit, 165 in surplus, 51 broadly
consistent.**

**The asymmetry is structural and is not smoothed over.** Priced-in growth is
bounded above by the cost of equity; sustainable growth is unbounded. Surpluses
therefore outnumber deficits by construction, and the deficit side is where the
screen actually bites.

**Sensitivity.** The cost of equity is swept from 7% to 12% in
`outputs/tables/cost_of_equity_sensitivity.csv`. Because a change in `r` shifts
every company's priced-in growth by the same constant, the ranking is invariant —
Spearman correlation against the 9% base case is 1.000 at every rate, computed
rather than asserted. What moves is only the count either side of the threshold:
34 deficits at 7%, 103 at 12%. The assumption determines where the line is drawn
and cannot determine which side of it a company falls on relative to another.

| Cost of equity | Deficit | Surplus | Consistent | Rank corr. |
|---|---|---|---|---|
| 7% | 34 | 193 | 58 | 1.000 |
| 8% | 53 | 182 | 50 | 1.000 |
| **9%** | **69** | **165** | **51** | — |
| 10% | 86 | 150 | 49 | 1.000 |
| 11% | 92 | 133 | 60 | 1.000 |
| 12% | 103 | 117 | 65 | 1.000 |

## 7. Peer benchmarking

`screen.peer_table`. Ranks are percentile ranks **within** the sector, not against
the index, because the question is which of these companies is the better holding
against its own alternatives. The composite is an unweighted mean of three
percentile ranks — EBITDA margin, ROE, earnings yield. Equal weights are a
decision, not a result; the three component ranks are reported alongside so
anyone can reweight.

The classification cascade is: above the sector median on all three is *quality at
a discount*; above on both quality measures but not on price is *quality, fully
priced*; above on price alone is *cheap on price alone*; the remainder is
*expensive without the quality*. Information Technology splits 10 / 12 / 19 / 15.

## 8. Known limitations

1. **Single undated snapshot.** No trend, no seasonality, no prior period, and no
   way to verify the vintage from inside the file.
2. **Retained sample selected towards profitability.** The source nulls the P/E
   where earnings are negative, so all 28 loss-making constituents leave the
   return-based analyses. Every quality conclusion is a conclusion about
   profitable companies.
3. **Trailing earnings only.** Nothing distinguishes a company that is cheap
   because it is declining from one that is cheap and mispriced.
4. **ROE is inflated where book equity has been repurchased.** 32 constituents
   have negative book equity and 60 more show ROE above 40%. Both groups are
   excluded from the relevant analyses, but the survivors are not immune to the
   same effect in milder form.
5. **The margin comparison is not like-for-like across all eleven sectors.**
   Financials and Real Estate are flagged and the headline test is re-run without
   them; no such correction is available within the remaining nine.
6. **Cross-sectional association throughout.** The negative margin coefficient
   describes the sample; it is not an estimate of what would happen to a
   company's multiple if its margin rose.
7. **Sub-industry results rest on thin groups.** The ANOVA at sub-industry level
   uses groups of three or more (62 groups, 367 observations); the reported table
   uses five or more (33 groups). Omega-squared is quoted alongside eta-squared
   throughout because the correction is large at that group count.
8. **The vendor's P/E is price over trailing EPS.** Every derived earnings figure
   inherits whatever period the EPS covers, and the extract does not say which.

## 9. Reproducibility

Seed fixed at 20260214 in `config.py`. `make analysis` regenerates every table,
figure and number in the report pack from the raw extract.
`outputs/metrics.json` is the single source for every figure quoted in the README
and the executive summary — none of them are typed by hand. The sub-industry
mapping is exported to `outputs/tables/gics_sector_mapping.csv` on each run so the
SQL staging model loads exactly the mapping the Python path uses.

The SQL in `sql/` reimplements the staging model, the derivations and the metric
definitions in PostgreSQL, and each file ends with assertion queries that should
return zero failures: the shares identity, the absence of negative P/E, the
price-over-EPS construction of the multiple, the payout identity, and the
log(P/B) = log(ROE) + log(P/E) identity underlying §5.4.
