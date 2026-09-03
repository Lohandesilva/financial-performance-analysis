# S&P 500 profitability and valuation: what the screen is worth

**To:** Head of Equity Research
**From:** Lohan De Silva
**Re:** Whether sector explains margin, whether the market pays for quality, and what to screen on instead

---

## The position

Two beliefs sit underneath most of how a large-cap book gets constructed: that
margin is a property of the sector, and that the market pays a premium for the
companies that earn the best returns. Tested against 503 index constituents, the
first is a quarter true and the second is not true on the earnings multiple at
all.

**Sector explains 26% of the variation in EBITDA margin** — statistically
unambiguous (F = 15.7, p < 0.001) and far smaller than the 43-point range between
sector medians implies. Three quarters of margin variance sits *inside* sectors.
The median sector spans 15.6 points between its quartiles; the sector medians
themselves span 10.7. Knowing where a company sits within its sector tells you
more than knowing the sector.

And two of the eleven sectors carry most of what is left. A bank reports interest
income and a REIT reports rent against a depreciating asset base, so neither
"margin" is comparable to an operating company's. **Strip Financials and Real
Estate out and sector explains 15%.**

## What the market actually pays for

Regressing the log earnings multiple on EBITDA margin and size across 354
companies: the margin coefficient is **−0.61** (p = 0.002) and the size
coefficient is **+0.14** (p < 0.001). Holding size constant, twenty points more
EBITDA margin is associated with an 11% *lower* earnings multiple. Median trailing
P/E goes from 20x in the smallest market-capitalisation quintile to 31x in the
largest. The size effect survives sector fixed effects; the margin effect stays
negative.

The counterpart is what does not show up. Earnings yield regressed on ROE and net
margin — the specification most quality screens rest on — returns **R² = 0.002**
with neither term significant. There is no quality premium in the earnings
multiple in this snapshot.

Where quality *is* priced, it is priced almost mechanically. Because
ROE = (P/B)/(P/E), the identity log(P/B) = log(ROE) + log(P/E) holds exactly, and
decomposing the variance shows **91% of the dispersion in the price-to-book
multiple is dispersion in return on equity**, with a −44% covariance term
offsetting it. Higher-ROE companies trade on lower earnings multiples
(correlation −0.32). A price-to-book screen is close to a ROE ranking with a
valuation adjustment working against it.

## What to do

**1. Screen margin at sub-industry level, not sector level.** Sub-industry
reaches η² = 0.59 against sector's 0.26. A sector-level margin assumption is
buying a quarter of the effect it thinks it is buying.

**2. Work the funding-deficit list as a capital question.** Of 285 screened
companies, **69 are priced above the growth their own balance sheet can fund** —
$4.2tn, 6.4% of index capitalisation. Their median payout is 66% against 22% for
the surplus group; their median ROE is 8.8% against 21.2%.

| | Deficit list | Surplus list |
|---|---|---|
| Companies | **69** | 165 |
| Median payout ratio | **66%** | 22% |
| Median return on equity | **8.8%** | 21.2% |
| Market capitalisation | **$4.2tn** | — |

**Twenty-one of the 29 screened utilities are on the deficit list** — median
payout 65%, median ROE 9.6%, median dividend yield 3.3%, funding 3.5 points of
growth against the 6.8 the price requires. The question for each is where the
capital for the priced growth is coming from.

**3. Take the high-margin, low-multiple names where they exist, because no
premium is being charged for them.** In Information Technology — the largest
sector at 36.9% of index capitalisation — only 10 of 56 companies clear the
sector median on EBITDA margin, ROE and earnings yield together.

## The part that is counter-intuitive

The instinct is to read a low earnings multiple on a high-quality company as an
opportunity the market has missed. On this data that reading has the sign wrong.
The market is *systematically* assigning lower earnings multiples to
higher-return companies — not failing to notice them.

The likely mechanism is visible in the same identity. Return on equity in this
sample is inflated wherever book equity has been bought back towards zero: 32
constituents carry outright negative book equity, and 60 more show a return on
equity above 40%. For those companies a high ROE is partly an artefact of a small
denominator, and a lower earnings multiple is the market pricing the earnings
rather than the ratio. That is a reason to be careful with ROE screens, not a
reason to buy every low-multiple high-ROE name.

## Risks to the case

**The snapshot is undated.** The file carries no as-of column and the publisher
overwrites it in place. Every number here is one point in time and cannot be
compared to a prior period. Seventeen constituents carry no market data at all,
several of them companies that have already left the index through acquisition,
which means the roster and the price vector were assembled at different moments.

**The universe is selected towards profitability.** The source nulls the P/E
where trailing earnings are negative rather than reporting it negative, so all 28
loss-making constituents drop out of any return-based analysis. A quality
conclusion drawn on the survivors is a conclusion about profitable companies.

**Everything is trailing and cross-sectional.** There are no forecasts and no
prior period, so nothing here separates a company that is cheap because it is
declining from one that is cheap and mispriced. The screen output is a list of
questions to put to companies, not a list of positions.

**The cost of equity does not matter as much as it looks like it should.**
Priced-in growth is r − (E/P) × b, so changing r shifts every company by the same
constant. Between 7% and 12% the deficit count moves from 34 to 103 and the rank
correlation against the base case stays at 1.000. The threshold is an argument;
the ordering is not.

## Next

1. Rebuild the margin screen on sub-industry and re-run the sector attribution
   on the book. The sector-level assumption is costing more than it is worth.
2. Put the funding question to the 21 flagged utilities directly: rate base
   growth, planned issuance, and whether the payout is expected to hold.
3. Get a second period. Every conclusion here is cross-sectional, and the one
   thing that would change the reading of the margin dispersion is knowing
   whether within-sector spread is widening.

---

Derivations, method and limitations: `reports/technical-appendix.md`.
All figures reproduce from `make analysis`.
